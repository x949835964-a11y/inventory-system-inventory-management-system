"""Report queries: turn database rows into the plain report objects the exporters use."""
from datetime import date, timedelta

from flask import current_app
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Category, MovementType, Product, StockMovement
from app.services.exceptions import BusinessRuleError
from app.services.report_types import InventoryReport, InventoryRow, MovementRow, MovementsReport
from app.utils.dates import local_day_start_utc, to_local, utc_now

MAX_RANGE_DAYS = 366  # a bigger PDF would take long to build and be useless to read


def _config():
    return current_app.config["APP_TIMEZONE"], current_app.config["BUSINESS_NAME"]


def _now_local(tz_name: str):
    return to_local(utc_now(), tz_name).replace(tzinfo=None)


def inventory_report(*, category_id: int | None = None, stock: str = "") -> InventoryReport:
    """Current stock of every active product, optionally by category or only those needing restock."""
    tz_name, business = _config()
    query = (
        select(Product)
        .options(joinedload(Product.category), joinedload(Product.supplier))
        .where(Product.is_active.is_(True))
        .order_by(Product.name)
    )
    filters = []
    if category_id:
        category = db.session.get(Category, category_id)
        if category is None:
            raise BusinessRuleError("La categoría seleccionada no existe.")
        query = query.where(Product.category_id == category_id)
        filters.append(f"Categoría: {category.name}")
    if stock == "low":
        query = query.where(Product.stock <= Product.min_stock)
        filters.append("Solo productos por reponer")

    rows = [
        InventoryRow(
            sku=p.sku,
            name=p.name,
            category=p.category.name,
            supplier=p.supplier.name if p.supplier else "",
            unit=p.unit,
            stock=p.stock,
            min_stock=p.min_stock,
            purchase_price=p.purchase_price,
            sale_price=p.sale_price,
        )
        for p in db.session.execute(query).scalars()
    ]
    return InventoryReport(business_name=business, generated_at=_now_local(tz_name),
                           filters=filters or ["Todos los productos activos"], rows=rows)


def movements_report(*, date_from: date, date_to: date, movement_type: str = "", search: str = "") -> MovementsReport:
    """Movements between two local calendar days (inclusive), oldest first."""
    if date_from > date_to:
        raise BusinessRuleError("La fecha inicial no puede ser posterior a la fecha final.")
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise BusinessRuleError(f"El rango máximo es de {MAX_RANGE_DAYS} días. Divide el reporte en periodos más cortos.")

    tz_name, business = _config()
    query = (
        select(StockMovement)
        .join(StockMovement.product)
        .options(joinedload(StockMovement.product), joinedload(StockMovement.user))
        .where(
            StockMovement.movement_date >= local_day_start_utc(date_from, tz_name),
            StockMovement.movement_date < local_day_start_utc(date_to + timedelta(days=1), tz_name),
        )
        .order_by(StockMovement.movement_date, StockMovement.id)
    )
    filters = [f"Del {date_from:%d/%m/%Y} al {date_to:%d/%m/%Y}"]
    if movement_type in {t.value for t in MovementType}:
        direction = MovementType(movement_type)
        query = query.where(StockMovement.movement_type == direction)
        filters.append(f"Solo {direction.label.lower()}s")
    if search:
        term = search.strip()
        query = query.where(or_(Product.name.icontains(term, autoescape=True), Product.sku.icontains(term, autoescape=True)))
        filters.append(f"Producto: «{term}»")

    rows = [
        MovementRow(
            moment=to_local(m.movement_date, tz_name).replace(tzinfo=None),
            sku=m.product.sku,
            product=m.product.name,
            unit=m.product.unit,
            is_entry=m.movement_type == MovementType.IN,
            reason=m.reason.label,
            quantity=m.quantity,
            unit_cost=m.unit_cost,
            stock_after=m.stock_after,
            user=m.user.username,
            notes=m.notes or "",
        )
        for m in db.session.execute(query).scalars()
    ]
    return MovementsReport(business_name=business, generated_at=_now_local(tz_name),
                           date_from=date_from, date_to=date_to, filters=filters, rows=rows)
