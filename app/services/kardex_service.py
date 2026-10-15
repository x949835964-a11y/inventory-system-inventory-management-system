"""Kardex: the chronological ledger of one product with opening and closing balances."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import MovementType, Product, StockMovement
from app.utils.dates import local_day_start_utc


@dataclass
class Kardex:
    product: Product
    date_from: date
    date_to: date
    opening_balance: Decimal
    rows: list[StockMovement] = field(default_factory=list)

    @property
    def total_in(self) -> Decimal:
        return sum((m.quantity for m in self.rows if m.movement_type == MovementType.IN), Decimal("0"))

    @property
    def total_out(self) -> Decimal:
        return sum((m.quantity for m in self.rows if m.movement_type == MovementType.OUT), Decimal("0"))

    @property
    def total_in_cost(self) -> Decimal:
        return sum((m.total_cost for m in self.rows if m.movement_type == MovementType.IN), Decimal("0.00"))

    @property
    def total_out_cost(self) -> Decimal:
        return sum((m.total_cost for m in self.rows if m.movement_type == MovementType.OUT), Decimal("0.00"))

    @property
    def closing_balance(self) -> Decimal:
        return self.rows[-1].stock_after if self.rows else self.opening_balance

    @property
    def is_consistent(self) -> bool:
        """Opening + entries - exits must equal the closing balance (a built-in audit check)."""
        return self.opening_balance + self.total_in - self.total_out == self.closing_balance


def build_kardex(product: Product, date_from: date, date_to: date, tz_name: str) -> Kardex:
    """Movements between two LOCAL calendar days (inclusive), with the balance before the range."""
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    start = local_day_start_utc(date_from, tz_name)
    end = local_day_start_utc(date_to + timedelta(days=1), tz_name)  # exclusive upper bound

    chronological = (StockMovement.movement_date, StockMovement.id)
    last_before = db.session.execute(
        select(StockMovement.stock_after)
        .where(StockMovement.product_id == product.id, StockMovement.movement_date < start)
        .order_by(*(col.desc() for col in chronological))
        .limit(1)
    ).scalar_one_or_none()

    rows = db.session.execute(
        select(StockMovement)
        .options(joinedload(StockMovement.user))
        .where(
            StockMovement.product_id == product.id,
            StockMovement.movement_date >= start,
            StockMovement.movement_date < end,
        )
        .order_by(*chronological)
    ).scalars().all()

    return Kardex(
        product=product,
        date_from=date_from,
        date_to=date_to,
        opening_balance=last_before if last_before is not None else Decimal("0"),
        rows=list(rows),
    )
