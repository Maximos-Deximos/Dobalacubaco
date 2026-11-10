# Testes dos contratos Pydantic iniciais.

import pytest
from pydantic import ValidationError

from app.schemas.form import FieldMapping, FillPlan
from app.schemas.profile import ProfileCreate


# Confere a validação mínima de e-mail.
def test_profile_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        ProfileCreate(email="sem-arroba")


# Confere que um campo não pode aparecer duas vezes no plano.
def test_fill_plan_rejects_duplicate_field_ids() -> None:
    with pytest.raises(ValidationError):
        FillPlan(
            url="https://example.com",
            fields=[
                FieldMapping(field_id="f_1"),
                FieldMapping(field_id="f_1"),
            ],
        )
