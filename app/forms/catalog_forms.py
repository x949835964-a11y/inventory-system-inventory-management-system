"""Category and supplier forms."""
from wtforms import BooleanField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp, ValidationError

from app.forms.base import BaseForm
from app.utils.peru import ruc_problem


def valid_ruc(_form, field) -> None:
    ruc = (field.data or "").replace(" ", "")
    if ruc:
        problem = ruc_problem(ruc)
        if problem:
            raise ValidationError(problem)


class CategoryForm(BaseForm):
    name = StringField("Nombre", validators=[DataRequired(), Length(min=2, max=80)])
    description = TextAreaField("Descripción", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Guardar")


class SupplierForm(BaseForm):
    name = StringField("Razón social o nombre", validators=[DataRequired(), Length(min=2, max=120)])
    ruc = StringField("RUC", validators=[Optional(), valid_ruc])
    contact_name = StringField("Persona de contacto", validators=[Optional(), Length(max=120)])
    phone = StringField(
        "Teléfono",
        validators=[
            Optional(),
            Regexp(r"^[0-9+()\-\s]{6,20}$", message="Usa solo números, espacios, +, - o paréntesis."),
        ],
    )
    email = StringField("Correo", validators=[Optional(), Email(message="Correo no válido."), Length(max=120)])
    address = StringField("Dirección", validators=[Optional(), Length(max=255)])
    is_active = BooleanField("Proveedor activo", default=True)
    submit = SubmitField("Guardar")
