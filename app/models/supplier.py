"""Product suppliers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Supplier(TimestampMixin, db.Model):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # Peruvian tax ID: 11 digits. Optional (small suppliers may not have one), unique when present.
    ruc: Mapped[str | None] = mapped_column(String(11), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    contact_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    products: Mapped[list[Product]] = relationship(back_populates="supplier", passive_deletes="all")

    @validates("ruc", "email")
    def _empty_to_none(self, _key: str, value: str | None) -> str | None:
        # An empty form field must become NULL, otherwise two "" RUCs would violate UNIQUE.
        value = (value or "").strip()
        return value or None

    def __repr__(self) -> str:
        return f"<Supplier {self.name}>"
