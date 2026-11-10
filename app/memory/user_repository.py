# Repositório responsável pela leitura e escrita de perfis.

from __future__ import annotations

from sqlalchemy import select, update

from app.memory.database import session_scope
from app.memory.models import UserProfileModel
from app.schemas.profile import ProfileCreate, ProfilePatch, UserProfile


# Erro lançado quando o perfil solicitado não existe.
class ProfileNotFoundError(LookupError):
    pass


# Converte o modelo ORM no contrato Pydantic usado pela aplicação.
def _to_schema(model: UserProfileModel) -> UserProfile:
    return UserProfile.model_validate(model)


# Repositório de perfis com suporte ao perfil padrão e a múltiplos perfis futuros.
class UserRepository:
    # Recebe uma URL opcional para permitir testes isolados.
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    # Busca o perfil marcado como padrão.
    def get_default(self) -> UserProfile | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(UserProfileModel)
                .where(UserProfileModel.is_default.is_(True))
                .order_by(UserProfileModel.id)
                .limit(1)
            )
            return _to_schema(model) if model is not None else None

    # Busca um perfil pelo nome.
    def get_by_name(self, name: str) -> UserProfile | None:
        with session_scope(self.database_url) as session:
            model = session.scalar(
                select(UserProfileModel).where(UserProfileModel.name == name)
            )
            return _to_schema(model) if model is not None else None

    # Lista todos os perfis cadastrados.
    def list_all(self) -> list[UserProfile]:
        with session_scope(self.database_url) as session:
            models = session.scalars(
                select(UserProfileModel).order_by(UserProfileModel.id)
            ).all()
            return [_to_schema(model) for model in models]

    # Cria um perfil e garante que exista apenas um perfil padrão.
    def create(self, data: ProfileCreate) -> UserProfile:
        with session_scope(self.database_url) as session:
            if data.is_default:
                session.execute(
                    update(UserProfileModel).values(is_default=False)
                )

            model = UserProfileModel(**data.model_dump())
            session.add(model)
            session.flush()
            return _to_schema(model)

    # Atualiza parcialmente um perfil.
    # Os dicionários links e custom_answers são mesclados, não substituídos.
    def update(self, profile_id: int, patch: ProfilePatch) -> UserProfile:
        with session_scope(self.database_url) as session:
            model = session.get(UserProfileModel, profile_id)
            if model is None:
                raise ProfileNotFoundError(
                    f"Perfil {profile_id} não encontrado."
                )

            changes = patch.model_dump(exclude_unset=True)
            new_is_default = changes.pop("is_default", None)

            for key, value in changes.items():
                if key in {"links", "custom_answers"}:
                    if value is None:
                        continue
                    current = dict(getattr(model, key) or {})
                    current.update(value)
                    setattr(model, key, current)
                else:
                    setattr(model, key, value)

            if new_is_default is True:
                session.execute(
                    update(UserProfileModel)
                    .where(UserProfileModel.id != profile_id)
                    .values(is_default=False)
                )
                model.is_default = True
            elif new_is_default is False:
                model.is_default = False

            session.flush()
            return _to_schema(model)

    # Cria o perfil padrão se ainda não existir.
    # Devolve o perfil e um booleano indicando se ele foi criado agora.
    def ensure_default(
        self, data: ProfileCreate | None = None
    ) -> tuple[UserProfile, bool]:
        existing = self.get_default()
        if existing is not None:
            return existing, False

        if data is None:
            data = ProfileCreate(name="default", is_default=True)

        existing_by_name = self.get_by_name(data.name)
        if existing_by_name is not None:
            updated = self.update(
                existing_by_name.id,
                ProfilePatch(is_default=True),
            )
            return updated, False

        return self.create(data), True
