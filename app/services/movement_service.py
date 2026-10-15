"""Read-side queries for the movements screen (writes live in stock_service)."""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import REASONS_BY_TYPE, MovementReason, MovementType, Product, StockMovement, User
from app.utils.dates import local_day_start_utc
from app.utils.formatters import quantity as fmt_qty


@dataclass(frozen=True)
class MovementFilters:
    search: str = ""                  # product name or SKU
    movement_type: str = ""           # "" | "in" | "out"
    reason: str = ""                  # MovementReason value or ""
    date_from: date | None = None     # local calendar days, inclusive
    date_to: date | None = None


def paginate_movements(filters: MovementFilters, tz_name: str, page: int = 1, per_page: int = 15):
    query = (
        select(StockMovement)
        .join(StockMovement.product)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.user))
        .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
    )
    if filters.search:
        term = filters.search.strip()
        query = query.where(or_(Product.name.icontains(term, autoescape=True), Product.sku.icontains(term, autoescape=True)))
    if filters.movement_type in {t.value for t in MovementType}:
        query = query.where(StockMovement.movement_type == MovementType(filters.movement_type))
    if filters.reason in {r.value for r in MovementReason}:
        query = query.where(StockMovement.reason == MovementReason(filters.reason))
    if filters.date_from:
        query = query.where(StockMovement.movement_date >= local_day_start_utc(filters.date_from, tz_name))
    if filters.date_to:
        query = query.where(StockMovement.movement_date < local_day_start_utc(filters.date_to + timedelta(days=1), tz_name))
    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def product_choices() -> list[tuple[int, str]]:
    """Active products for the movement form, showing the current stock to help the user."""
    products = db.session.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.name)).scalars()
    return [(p.id, f"{p.sku} — {p.name} (stock: {fmt_qty(p.stock)} {p.unit})") for p in products]


def reason_choices(movement_type: MovementType, user: User) -> list[tuple[str, str]]:
    """Reasons valid for the direction; adjustments only for administrators."""
    return [
        (r.value, r.label)
        for r in REASONS_BY_TYPE[movement_type]
        if r != MovementReason.ADJUSTMENT or user.is_admin
    ]
