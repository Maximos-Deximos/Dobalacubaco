# Modelos de dados do perfil do usuário.

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

PROFILE_KEYS: tuple[str, ...] = (
    "full_name",
    "first_name",
    "last_name",
    "email",
    "phone",
    "organization",
    "role",
    "address",
    "city",
    "state",
    "postal_code",
    "country",
    "birth_date",
    "links",
    "skills",
)


# Campos compartilhados entre criação, edição e leitura do perfil.
class ProfileBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    organization: str | None = None
    role: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    birth_date: date | None = None
    links: dict[str, str] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    custom_answers: dict[str, str] = Field(default_factory=dict)

    # Faz uma validação mínima para evitar e-mails claramente inválidos.
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value and "@" not in value:
            raise ValueError("E-mail inválido: falta o caractere '@'.")
        return value

    # Normaliza dicionários recebidos com chaves ou valores não textuais.
    @field_validator("links", "custom_answers", mode="before")
    @classmethod
    def normalize_string_dict(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return {str(key): str(item) for key, item in value.items()}
        raise ValueError("O campo deve ser um dicionário chave-valor.")


# Dados necessários para criar um perfil.
class ProfileCreate(ProfileBase):
    name: str = "default"
    is_default: bool = True


# Atualização parcial do perfil; campos ausentes não são alterados.
class ProfilePatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    is_default: bool | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    organization: str | None = None
    role: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    birth_date: date | None = None
    links: dict[str, str] | None = None
    skills: list[str] | None = None
    custom_answers: dict[str, str] | None = None


# Perfil completo devolvido pela camada de persistência.
class UserProfile(ProfileBase):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: int
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
