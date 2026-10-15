"""Custom WTForms validators."""
from wtforms.validators import ValidationError

from app.utils.security import password_problem


def strong_password(_form, field) -> None:
    problem = password_problem(field.data or "")
    if problem:
        raise ValidationError(problem)
