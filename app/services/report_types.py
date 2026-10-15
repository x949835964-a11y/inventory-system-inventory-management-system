"""Plain data handed to the exporters.

No database or Flask imports here on purpose: the Excel and PDF builders only receive these
objects, so they can be tested (and reused) without a database.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

FRACTIONAL_UNITS = {"KG", "G", "L", "ML", "M"}


@dataclass(frozen=True)
class InventoryRow:
    sku: str
    name: str
    category: str
    supplier: str
    unit: str
    stock: Decimal
    min_stock: Decimal
    purchase_price: Decimal
    sale_price: Decimal

    @property
    def stock_value(self) -> Decimal:
        return (self.stock * self.purchase_price).quantize(Decimal("0.01"))

    @property
    def status(self) -> str:
        if self.stock <= 0:
            return "Agotado"
        if self.stock <= self.min_stock:
            return "Stock bajo"
        return "Disponible"

    @property
    def allows_fractions(self) -> bool:
        return self.unit in FRACTIONAL_UNITS


@dataclass
class InventoryReport:
    business_name: str
    generated_at: datetime          # local time
    filters: list[str]              # human-readable, e.g. ["Categoría: Abarrotes"]
    rows: list[InventoryRow] = field(default_factory=list)

    @property
    def total_value(self) -> Decimal:
        return sum((r.stock_value for r in self.rows), Decimal("0.00"))

    @property
    def low_stock_count(self) -> int:
        return sum(1 for r in self.rows if r.status != "Disponible")

    @property
    def out_of_stock_count(self) -> int:
        return sum(1 for r in self.rows if r.status == "Agotado")


@dataclass(frozen=True)
class MovementRow:
    moment: datetime                # local time
    sku: str
    product: str
    unit: str
    is_entry: bool
    reason: str
    quantity: Decimal
    unit_cost: Decimal
    stock_after: Decimal
    user: str
    notes: str

    @property
    def type_label(self) -> str:
        return "Entrada" if self.is_entry else "Salida"

    @property
    def total_cost(self) -> Decimal:
        return (self.quantity * self.unit_cost).quantize(Decimal("0.01"))

    @property
    def allows_fractions(self) -> bool:
        return self.unit in FRACTIONAL_UNITS


# Every (type, reason) pair that can exist, in a stable order for the summaries.
REASON_SUMMARY_ORDER = [
    ("Entrada", "Compra"),
    ("Entrada", "Devolución de cliente"),
    ("Entrada", "Ajuste de inventario"),
    ("Salida", "Venta"),
    ("Salida", "Merma"),
    ("Salida", "Devolución a proveedor"),
    ("Salida", "Ajuste de inventario"),
]


@dataclass
class MovementsReport:
    business_name: str
    generated_at: datetime
    date_from: date
    date_to: date
    filters: list[str]
    rows: list[MovementRow] = field(default_factory=list)

    def _sum(self, is_entry: bool) -> Decimal:
        return sum((r.total_cost for r in self.rows if r.is_entry == is_entry), Decimal("0.00"))

    @property
    def total_in_value(self) -> Decimal:
        return self._sum(True)

    @property
    def total_out_value(self) -> Decimal:
        return self._sum(False)

    @property
    def entry_count(self) -> int:
        return sum(1 for r in self.rows if r.is_entry)

    @property
    def exit_count(self) -> int:
        return sum(1 for r in self.rows if not r.is_entry)

    def by_reason(self) -> list[tuple[str, str, int, Decimal]]:
        """(type, reason, count, value at cost) for every pair, zeros included."""
        result = []
        for type_label, reason in REASON_SUMMARY_ORDER:
            matching = [r for r in self.rows if r.type_label == type_label and r.reason == reason]
            result.append((type_label, reason, len(matching), sum((r.total_cost for r in matching), Decimal("0.00"))))
        return result
