"""Authentication logic, independent from Flask routes."""
from functools import cache

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User
from app.services.exceptions import AuthenticationError
from app.utils.dates import utc_now

INVALID_CREDENTIALS = "Usuario o contraseña incorrectos."


@cache
def _dummy_hash() -> str:
    return generate_password_hash("timing-equalizer-not-a-real-password")


def authenticate(username: str, password: str) -> User:
    """Return the user if the credentials are valid; raise AuthenticationError otherwise."""
    username = (username or "").strip().lower()
    user = db.session.execute(select(User).filter_by(username=username)).scalar_one_or_none()

    if user is None:
        # Hash anyway so "unknown user" takes as long as "wrong password":
        # response time must not reveal which usernames exist.
        check_password_hash(_dummy_hash(), password)
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not user.check_password(password):
        raise AuthenticationError(INVALID_CREDENTIALS)

    # Only revealed after a correct password, so it doesn't leak which accounts exist.
    if not user.is_active:
        raise AuthenticationError("Tu cuenta está desactivada. Contacta al administrador.")

    user.last_login_at = utc_now()
    db.session.commit()
    return user
