"""Reusable column sets and helpers for models."""
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.dates import utc_now


def enum_column(enum_cls: type[Enum], name: str) -> SAEnum:
    """Store the enum's value (e.g. 'admin') instead of its member name (e.g. 'ADMIN')."""
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
