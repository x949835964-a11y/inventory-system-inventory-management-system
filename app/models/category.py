"""Product categories."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Category(TimestampMixin, db.Model):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    products: Mapped[list[Product]] = relationship(back_populates="category", passive_deletes="all")

    @validates("name")
    def _strip_name(self, _key: str, value: str) -> str:
        return value.strip()

    def __repr__(self) -> str:
        return f"<Category {self.name}>"
