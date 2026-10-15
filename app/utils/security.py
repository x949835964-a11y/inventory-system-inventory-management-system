"""Security helpers shared by forms, routes and the CLI."""
import re
from urllib.parse import urlsplit

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def password_problem(password: str) -> str | None:
    """Return a message describing why the password is weak, or None if it is acceptable."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"La contraseña no puede superar {PASSWORD_MAX_LENGTH} caracteres."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "La contraseña debe combinar letras y números."
    return None


def is_safe_redirect(target: str | None) -> bool:
    """Allow only relative paths on this site, preventing open redirects via ?next=."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return False
    parts = urlsplit(target)
    return not parts.scheme and not parts.netloc
