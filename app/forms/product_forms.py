"""Product forms. There is no "stock" field on purpose: stock only changes through movements."""
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, Regexp

from app.forms.base import BaseForm
from app.forms.fields import LocalizedDecimalField, max_decimals
from app.models import UNITS

NOT_NEGATIVE = NumberRange(min=0, message="Debe ser mayor o igual a 0.")


class ProductForm(BaseForm):
    sku = StringField(
        "Código / SKU",
        validators=[
            DataRequired(),
            Regexp(r"^[A-Za-z0-9._-]{2,40}$", message="De 2 a 40 caracteres: letras, números, punto o guiones."),
        ],
    )
    name = StringField("Nombre", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Descripción", validators=[Optional(), Length(max=2000)])
    # Choices are loaded in the route (they come from the database).
    category_id = SelectField("Categoría", coerce=int, validators=[DataRequired(message="Selecciona una categoría.")])
    supplier_id = SelectField("Proveedor", coerce=int)
    unit = SelectField("Unidad de medida", choices=UNITS, default="UND")
    purchase_price = LocalizedDecimalField(
        "Precio de compra (S/)", places=2, validators=[InputRequired("Ingresa el precio."), NOT_NEGATIVE, max_decimals(2)]
    )
    sale_price = LocalizedDecimalField(
        "Precio de venta (S/)", places=2, validators=[InputRequired("Ingresa el precio."), NOT_NEGATIVE, max_decimals(2)]
    )
    min_stock = LocalizedDecimalField(
        "Stock mínimo", places=None, default=0, validators=[InputRequired(), NOT_NEGATIVE, max_decimals(3)]
    )
    submit = SubmitField("Guardar")


class ProductCreateForm(ProductForm):
    initial_stock = LocalizedDecimalField(
        "Stock inicial", places=None, default=0, validators=[Optional(), NOT_NEGATIVE, max_decimals(3)]
    )
