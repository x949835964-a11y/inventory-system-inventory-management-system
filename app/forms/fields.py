"""Custom form fields and validators for numbers."""
from wtforms import DecimalField
from wtforms.validators import ValidationError


class LocalizedDecimalField(DecimalField):
    """Decimal field that accepts '18,50' as well as '18.50' (comma is common in Peru).

    With places=None it shows quantities without useless zeros: 5.000 -> '5', 2.500 -> '2.5'.
    """

    def process_formdata(self, valuelist):
        if valuelist:
            valuelist = [valuelist[0].strip().replace(" ", "").replace(",", ".")]
        super().process_formdata(valuelist)

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        if self.data is not None and self.places is None:
            text = format(self.data, "f")
            return text.rstrip("0").rstrip(".") if "." in text else text
        return super()._value()


def max_decimals(places: int):
    """Reject values with more decimals than the database column stores (instead of rounding silently)."""

    def _validator(_form, field):
        if field.data is not None and field.data.as_tuple().exponent < -places:
            raise ValidationError(f"Máximo {places} decimales.")

    return _validator
