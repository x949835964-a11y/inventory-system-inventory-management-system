"""Login and own-password forms."""
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length

from app.forms.base import BaseForm
from app.forms.validators import strong_password


class LoginForm(BaseForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(max=50)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Recordarme")
    submit = SubmitField("Ingresar")


class ChangePasswordForm(BaseForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired(), strong_password])
    confirm_password = PasswordField(
        "Confirmar nueva contraseña",
        validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden.")],
    )
    submit = SubmitField("Cambiar contraseña")
