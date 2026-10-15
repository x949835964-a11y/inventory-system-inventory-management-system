"""Demo accounts for the public demo (DEMO_MODE=true).

In demo mode these accounts are shown on the login page and protected: visitors can use the
whole system, but cannot change their passwords, roles or status and lock everyone else out.
"""
from flask import current_app

from app.models import UserRole

# (username, full name, role, password). Only for demo data: never use these in a real shop.
DEMO_ACCOUNTS = [
    ("admin", "Administrador Demo", UserRole.ADMIN, "Admin123"),
    ("empleado", "Empleado Demo", UserRole.EMPLOYEE, "Empleado123"),
]
DEMO_USERNAMES = {username for username, *_ in DEMO_ACCOUNTS}


def is_protected_demo_user(user) -> bool:
    return bool(current_app.config.get("DEMO_MODE")) and user.username in DEMO_USERNAMES
