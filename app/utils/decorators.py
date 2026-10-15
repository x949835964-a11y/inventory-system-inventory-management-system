"""Authorization decorators for views."""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from app.models import UserRole


def role_required(*roles: UserRole):
    """Require login and one of the given roles. Use instead of @login_required, not with it."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)  # authenticated but not allowed
            return view(*args, **kwargs)

        # login_required runs first: anonymous users are sent to the login page (not a 403).
        return login_required(wrapped)

    return decorator


admin_required = role_required(UserRole.ADMIN)
