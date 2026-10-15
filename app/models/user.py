"""System users and their roles."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager
from app.models.mixins import TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.stock_movement import StockMovement


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"

    @property
    def label(self) -> str:
        return {"admin": "Administrador", "employee": "Empleado"}[self.value]


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"), default=UserRole.EMPLOYEE, nullable=False
    )
    # Overrides UserMixin.is_active: Flask-Login refuses to log in inactive users.
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    movements: Mapped[list[StockMovement]] = relationship(back_populates="user", passive_deletes="all")

    @validates("username")
    def _normalize_username(self, _key: str, value: str) -> str:
        return value.strip().lower()

    def set_password(self, password: str) -> None:
        # Werkzeug uses scrypt with a random salt; we never store the plain password.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    # Returning None for inactive users ends their open sessions on the next request,
    # so deactivating an account takes effect immediately.
    user = db.session.get(User, int(user_id))
    return user if user is not None and user.is_active else None
