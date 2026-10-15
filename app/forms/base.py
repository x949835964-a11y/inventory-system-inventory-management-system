"""Base form: built-in validation messages in Spanish ("Este campo es obligatorio.")."""
from flask_wtf import FlaskForm


class BaseForm(FlaskForm):
    class Meta:
        # Uses the translations that ship with WTForms (requires WTF_I18N_ENABLED = False,
        # otherwise Flask-WTF would look for Flask-Babel instead).
        locales = ("es",)
