"""Products. Stock is changed only through StockService, never directly from a form."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.stock_movement import StockMovement
    from app.models.supplier import Supplier

# Units of measure (code, label). A fixed list: stable data that doesn't need its own CRUD.
UNITS = [
    ("UND", "Unidad"),
    ("KG", "Kilogramo"),
    ("G", "Gramo"),
    ("L", "Litro"),
    ("ML", "Mililitro"),
    ("M", "Metro"),
    ("CAJA", "Caja"),
    ("PAQ", "Paquete"),
    ("DOC", "Docena"),
]
UNIT_CODES = {code for code, _ in UNITS}
UNIT_LABELS = dict(UNITS)
# Units that can be split (2.5 m of cable). Countable units (UND, CAJA...) only take whole numbers.
FRACTIONAL_UNITS = {"KG", "G", "L", "ML", "M"}

MONEY = Numeric(10, 2)     # up to 99,999,999.99
QUANTITY = Numeric(12, 3)  # allows fractions: 2.5 m of cable, 0.250 kg of cheese


class Product(TimestampMixin, db.Model):
    __tablename__ = "products"
    __table_args__ = (
        # Last line of defense: the database itself rejects invalid values.
        CheckConstraint("stock >= 0", name="stock_non_negative"),
        CheckConstraint("min_stock >= 0", name="min_stock_non_negative"),
        CheckConstraint("purchase_price >= 0", name="purchase_price_non_negative"),
        CheckConstraint("sale_price >= 0", name="sale_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    purchase_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="UND", nullable=False)
    stock: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("0"), server_default="0", nullable=False)
    min_stock: Mapped[Decimal] = mapped_column(QUANTITY, default=Decimal("0"), server_default="0", nullable=False)
    # Soft delete: products with history are deactivated, never removed.
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)

    category: Mapped[Category] = relationship(back_populates="products")
    supplier: Mapped[Supplier | None] = relationship(back_populates="products")
    movements: Mapped[list[StockMovement]] = relationship(back_populates="product", passive_deletes="all")

    @validates("sku")
    def _normalize_sku(self, _key: str, value: str) -> str:
        return value.strip().upper()

    @validates("unit")
    def _validate_unit(self, _key: str, value: str) -> str:
        if value not in UNIT_CODES:
            raise ValueError(f"Unidad de medida no válida: {value}")
        return value

    @property
    def allows_fractions(self) -> bool:
        return self.unit in FRACTIONAL_UNITS

    @property
    def unit_label(self) -> str:
        return UNIT_LABELS.get(self.unit, self.unit)

    @property
    def is_out_of_stock(self) -> bool:
        return self.stock <= 0

    @property
    def is_low_stock(self) -> bool:
        """True when the product needs restocking (stock at or below the minimum)."""
        return self.stock <= self.min_stock

    @property
    def stock_value(self) -> Decimal:
        """Inventory value at cost."""
        return (self.stock * self.purchase_price).quantize(Decimal("0.01"))

    @property
    def margin_percent(self) -> Decimal | None:
        """Gross margin over cost, e.g. 25.00 means the sale price is 25% above cost."""
        if not self.purchase_price:
            return None
        margin = (self.sale_price - self.purchase_price) / self.purchase_price * 100
        return margin.quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<Product {self.sku} stock={self.stock}>"
