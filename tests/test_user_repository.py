# Testes do repositório de perfis.

import pytest

from app.memory.database import init_db
from app.memory.user_repository import ProfileNotFoundError, UserRepository
from app.schemas.profile import ProfileCreate, ProfilePatch


# Prepara o banco e devolve um repositório pronto para uso.
@pytest.fixture
def repository(isolated_database: str) -> UserRepository:
    init_db(isolated_database)
    return UserRepository(isolated_database)


# Cria o perfil padrão apenas uma vez.
def test_ensure_default_is_idempotent(repository: UserRepository) -> None:
    profile, created = repository.ensure_default()
    assert created is True
    assert profile.name == "default"

    same_profile, created_again = repository.ensure_default()
    assert created_again is False
    assert same_profile.id == profile.id


# Atualiza campos fixos e mantém os demais inalterados.
def test_update_profile_fields(repository: UserRepository) -> None:
    profile, _ = repository.ensure_default()

    updated = repository.update(
        profile.id,
        ProfilePatch(full_name="Mizera Gorda", email="mizera@mizera.com"),
    )

    assert updated.full_name == "Mizera Gorda"
    assert updated.email == "mizera@mizera.com"
    assert updated.phone is None


# Mescla respostas personalizadas sem apagar as anteriores.
def test_update_merges_custom_answers(repository: UserRepository) -> None:
    profile, _ = repository.ensure_default()

    repository.update(
        profile.id,
        ProfilePatch(custom_answers={"team_name": "Gulosos.com"}),
    )
    updated = repository.update(
        profile.id,
        ProfilePatch(custom_answers={"tshirt_size": "M"}),
    )

    assert updated.custom_answers == {
        "team_name": "Gulosos.com",
        "tshirt_size": "M",
    }


# Persiste os dados entre sessões diferentes.
def test_profile_persists_between_sessions(isolated_database: str) -> None:
    init_db(isolated_database)
    repository = UserRepository(isolated_database)

    profile, _ = repository.ensure_default()
    repository.update(profile.id, ProfilePatch(full_name="Pessoa Teste"))

    other_repository = UserRepository(isolated_database)
    loaded = other_repository.get_default()

    assert loaded is not None
    assert loaded.full_name == "Pessoa Teste"


# Lança erro ao atualizar um perfil inexistente.
def test_update_missing_profile_raises(repository: UserRepository) -> None:
    with pytest.raises(ProfileNotFoundError):
        repository.update(999, ProfilePatch(full_name="Ninguém"))


# Mantém apenas um perfil padrão ao criar outro.
def test_create_default_unsets_previous_default(
    repository: UserRepository,
) -> None:
    first, _ = repository.ensure_default()
    second = repository.create(
        ProfileCreate(name="outro", is_default=True)
    )

    loaded_first = repository.get_by_name(first.name)

    assert second.is_default is True
    assert loaded_first is not None
    assert loaded_first.is_default is False
    assert repository.get_default() is not None
    assert repository.get_default().id == second.id
