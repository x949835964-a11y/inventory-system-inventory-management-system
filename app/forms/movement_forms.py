"""Inventory movement forms: one for entries and one for exits."""
from decimal import Decimal

from flask import current_app
from wtforms import BooleanField, DateField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, ValidationError

from app.forms.base import BaseForm
from app.forms.fields import LocalizedDecimalField, max_decimals
from app.utils.dates import local_today


def _today():
    return local_today(current_app.config["APP_TIMEZONE"])


def not_in_future(_form, field) -> None:
    if field.data and field.data > _today():
        raise ValidationError("La fecha no puede ser futura.")


class MovementForm(BaseForm):
    # Choices come from the database / user role; they are set in the route.
    product_id = SelectField("Producto", coerce=int, validators=[DataRequired(message="Selecciona un producto.")])
    reason = SelectField("Motivo")
    quantity = LocalizedDecimalField(
        "Cantidad",
        places=None,
        validators=[
            InputRequired("Ingresa la cantidad."),
            NumberRange(min=Decimal("0.001"), message="Debe ser mayor que 0."),
            max_decimals(3),
        ],
    )
    movement_date = DateField("Fecha", default=_today, validators=[DataRequired(), not_in_future])
    notes = TextAreaField("Observaciones", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Registrar")


class EntryForm(MovementForm):
    unit_cost = LocalizedDecimalField(
        "Costo unitario (S/)",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Debe ser mayor o igual a 0."), max_decimals(2)],
    )
    update_cost = BooleanField("Actualizar el precio de compra del producto con este costo", default=True)
    submit = SubmitField("Registrar entrada")


class ExitForm(MovementForm):
    submit = SubmitField("Registrar salida")
