"""User management rules. Only administrators reach these functions through the UI."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.demo import is_protected_demo_user
from app.extensions import db
from app.models import User, UserRole
from app.services.exceptions import BusinessRuleError

DEMO_LOCKED = "En la demo pública las cuentas de demostración no se pueden modificar."


def _ensure_not_demo(user: User) -> None:
    """Public demo: visitors may use everything, but can't lock others out of the demo accounts."""
    if is_protected_demo_user(user):
        raise BusinessRuleError(DEMO_LOCKED)


def paginate_users(page: int, per_page: int):
    query = select(User).order_by(User.is_active.desc(), User.full_name)
    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def create_user(*, username: str, full_name: str, password: str, role: UserRole) -> User:
    username = username.strip().lower()
    if db.session.execute(select(User.id).filter_by(username=username)).first():
        raise BusinessRuleError(f"El usuario '{username}' ya existe.")

    user = User(username=username, full_name=full_name.strip(), role=role)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Two admins creating the same username at the same moment: the UNIQUE index wins.
        db.session.rollback()
        raise BusinessRuleError(f"El usuario '{username}' ya existe.") from None
    return user


def update_user(user: User, *, full_name: str, role: UserRole, is_active: bool, acting_user: User) -> User:
    """Update profile, role and status. The username is immutable (it identifies the user in history)."""
    _ensure_not_demo(user)
    if user.id == acting_user.id and (role != UserRole.ADMIN or not is_active):
        # Since only active admins manage users and none can demote or disable themselves,
        # the system always keeps at least one active administrator.
        raise BusinessRuleError("No puedes quitarte el rol de administrador ni desactivar tu propia cuenta.")

    user.full_name = full_name.strip()
    user.role = role
    user.is_active = is_active
    db.session.commit()
    return user


def reset_password(user: User, new_password: str) -> None:
    """Admin sets a new password for a user (e.g. an employee who forgot it)."""
    _ensure_not_demo(user)
    user.set_password(new_password)
    db.session.commit()


def change_own_password(user: User, *, current_password: str, new_password: str) -> None:
    _ensure_not_demo(user)
    if not user.check_password(current_password):
        raise BusinessRuleError("La contraseña actual no es correcta.")
    if current_password == new_password:
        raise BusinessRuleError("La nueva contraseña debe ser distinta de la actual.")
    user.set_password(new_password)
    db.session.commit()
