"""Dashboard data: indicators, restock alerts, recent activity and the 30-day flow chart."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import MovementType, Product, StockMovement
from app.utils.dates import local_day_start_utc, local_today, to_local


@dataclass(frozen=True)
class Summary:
    product_count: int
    inventory_value: Decimal
    low_stock_count: int      # at or below minimum (includes out of stock)
    out_of_stock_count: int
    movements_today: int


def _money(value) -> Decimal:
    # SQLite returns floats for SUM(); MySQL returns Decimal. Normalize both.
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_summary(tz_name: str) -> Summary:
    """All product indicators in ONE query with conditional aggregation."""
    count, value, low, out = db.session.execute(
        select(
            func.count(Product.id),
            func.sum(Product.stock * Product.purchase_price),
            func.sum(case((Product.stock <= Product.min_stock, 1), else_=0)),
            func.sum(case((Product.stock <= 0, 1), else_=0)),
        ).where(Product.is_active.is_(True))
    ).one()
    today_start = local_day_start_utc(local_today(tz_name), tz_name)
    movements_today = db.session.execute(
        select(func.count(StockMovement.id)).where(StockMovement.movement_date >= today_start)
    ).scalar_one()
    return Summary(
        product_count=count,
        inventory_value=_money(value),
        low_stock_count=int(low or 0),
        out_of_stock_count=int(out or 0),
        movements_today=movements_today,
    )


def restock_list(limit: int = 8) -> list[Product]:
    """Products to restock: out of stock first, then the largest shortfall below the minimum."""
    return list(
        db.session.execute(
            select(Product)
            .options(joinedload(Product.category))
            .where(Product.is_active.is_(True), Product.stock <= Product.min_stock)
            .order_by(
                case((Product.stock <= 0, 0), else_=1),
                (Product.stock - Product.min_stock),
                Product.name,
            )
            .limit(limit)
        ).scalars()
    )


def recent_movements(limit: int = 8) -> list[StockMovement]:
    return list(
        db.session.execute(
            select(StockMovement)
            .options(joinedload(StockMovement.product), joinedload(StockMovement.user))
            .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
            .limit(limit)
        ).scalars()
    )


def daily_flow(tz_name: str, days: int = 30, today: date | None = None) -> dict:
    """Entries vs exits per LOCAL day, as value at cost (S/) and as number of movements.

    Value, not quantity: adding 5 kg to 3 boxes is meaningless, but soles always add up.
    Days are grouped in Python after converting each timestamp to local time; this stays
    portable (MySQL's CONVERT_TZ needs timezone tables that shared hosts often lack).
    """
    today = today or local_today(tz_name)
    first_day = today - timedelta(days=days - 1)
    rows = db.session.execute(
        select(
            StockMovement.movement_date,
            StockMovement.movement_type,
            StockMovement.quantity,
            StockMovement.unit_cost,
        ).where(
            StockMovement.movement_date >= local_day_start_utc(first_day, tz_name),
            StockMovement.movement_date < local_day_start_utc(today + timedelta(days=1), tz_name),
        )
    ).all()

    all_days = [first_day + timedelta(days=i) for i in range(days)]
    buckets = {day: {"in_value": Decimal("0"), "out_value": Decimal("0"), "in_count": 0, "out_count": 0} for day in all_days}
    for moment, movement_type, quantity, unit_cost in rows:
        bucket = buckets.get(to_local(moment, tz_name).date())
        if bucket is None:
            continue
        side = "in" if movement_type == MovementType.IN else "out"
        bucket[f"{side}_value"] += Decimal(str(quantity)) * Decimal(str(unit_cost))
        bucket[f"{side}_count"] += 1

    def series(key):
        return [float(_money(buckets[d][key])) if "value" in key else buckets[d][key] for d in all_days]

    return {
        "labels": [d.strftime("%d/%m") for d in all_days],
        "dates": [d.isoformat() for d in all_days],
        "in_value": series("in_value"),
        "out_value": series("out_value"),
        "in_count": series("in_count"),
        "out_count": series("out_count"),
        "total_in_value": float(_money(sum((b["in_value"] for b in buckets.values()), Decimal("0")))),
        "total_out_value": float(_money(sum((b["out_value"] for b in buckets.values()), Decimal("0")))),
    }
