"""Inventory movements (the ledger). Immutable: errors are fixed with an adjustment movement."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import CreatedAtMixin, enum_column
from app.utils.dates import utc_now

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class MovementType(str, enum.Enum):
    IN = "in"
    OUT = "out"

    @property
    def label(self) -> str:
        return {"in": "Entrada", "out": "Salida"}[self.value]


class MovementReason(str, enum.Enum):
    PURCHASE = "purchase"
    CUSTOMER_RETURN = "customer_return"
    SALE = "sale"
    SHRINKAGE = "shrinkage"
    SUPPLIER_RETURN = "supplier_return"
    ADJUSTMENT = "adjustment"

    @property
    def label(self) -> str:
        return {
            "purchase": "Compra",
            "customer_return": "Devolución de cliente",
            "sale": "Venta",
            "shrinkage": "Merma",
            "supplier_return": "Devolución a proveedor",
            "adjustment": "Ajuste de inventario",
        }[self.value]


# Which reasons make sense for each direction. Enforced by StockService (stage 5).
REASONS_BY_TYPE: dict[MovementType, tuple[MovementReason, ...]] = {
    MovementType.IN: (MovementReason.PURCHASE, MovementReason.CUSTOMER_RETURN, MovementReason.ADJUSTMENT),
    MovementType.OUT: (
        MovementReason.SALE,
        MovementReason.SHRINKAGE,
        MovementReason.SUPPLIER_RETURN,
        MovementReason.ADJUSTMENT,
    ),
}


class StockMovement(CreatedAtMixin, db.Model):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("stock_after >= 0", name="stock_after_non_negative"),
        # Kardex query: one product's movements within a date range, in order.
        Index("ix_stock_movements_product_date", "product_id", "movement_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    movement_type: Mapped[MovementType] = mapped_column(enum_column(MovementType, "movement_type"), nullable=False)
    reason: Mapped[MovementReason] = mapped_column(enum_column(MovementReason, "movement_reason"), nullable=False)
    # Always positive; movement_type gives the direction.
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Cost at the moment of the movement, so later price changes don't rewrite history.
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Snapshot of the stock before/after: the kardex reads them directly.
    stock_before: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    stock_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    # Business date chosen by the user (may differ from created_at if registered later).
    movement_date: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="movements")
    user: Mapped[User] = relationship(back_populates="movements")

    @property
    def signed_quantity(self) -> Decimal:
        """Positive for entries, negative for exits (handy for totals and charts)."""
        return self.quantity if self.movement_type == MovementType.IN else -self.quantity

    @property
    def total_cost(self) -> Decimal:
        return (self.quantity * self.unit_cost).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<StockMovement {self.movement_type.value} {self.quantity} product={self.product_id}>"
