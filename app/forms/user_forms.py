"""User management forms (administrators only)."""
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp

from app.forms.base import BaseForm
from app.forms.validators import strong_password
from app.models import UserRole

ROLE_CHOICES = [(role.value, role.label) for role in UserRole]


class UserCreateForm(BaseForm):
    username = StringField(
        "Usuario",
        validators=[
            DataRequired(),
            Regexp(
                r"^[A-Za-z0-9._-]{3,50}$",
                message="De 3 a 50 caracteres: letras, números, punto, guion o guion bajo.",
            ),
        ],
    )
    full_name = StringField("Nombre completo", validators=[DataRequired(), Length(max=120)])
    role = SelectField("Rol", choices=ROLE_CHOICES, default=UserRole.EMPLOYEE.value)
    password = PasswordField("Contraseña", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("password", message="Las contraseñas no coinciden.")],
    )
    submit = SubmitField("Crear usuario")


class UserEditForm(BaseForm):
    full_name = StringField("Nombre completo", validators=[DataRequired(), Length(max=120)])
    role = SelectField("Rol", choices=ROLE_CHOICES)
    is_active = BooleanField("Cuenta activa")
    submit = SubmitField("Guardar cambios")


class ResetPasswordForm(BaseForm):
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirmar contraseña",
        validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden.")],
    )
    submit = SubmitField("Restablecer contraseña")
