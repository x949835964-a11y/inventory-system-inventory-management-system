"""Product rules: unique SKU, valid prices and quantities, search/filters and soft delete.

Stock is NEVER edited here. It only changes through inventory movements; the one
exception is the initial stock, which is recorded as a movement in the same transaction.
"""
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    FRACTIONAL_UNITS,
    UNITS,
    Category,
    MovementReason,
    MovementType,
    Product,
    StockMovement,
    Supplier,
    User,
)
from app.services import stock_service
from app.services.exceptions import BusinessRuleError

UNIT_CODES = {code for code, _ in UNITS}
SORT_OPTIONS = {
    "name": (Product.name,),
    "sku": (Product.sku,),
    "stock": (Product.stock, Product.name),
}
EDITABLE_FIELDS = (
    "sku", "name", "description", "category_id", "supplier_id",
    "purchase_price", "sale_price", "unit", "min_stock",
)


@dataclass(frozen=True)
class ProductFilters:
    search: str = ""
    category_id: int | None = None
    stock: str = ""          # "" all | "low" at/below minimum | "out" zero stock
    status: str = "active"   # "active" | "inactive" | "all"
    sort: str = "name"


# --- Queries -------------------------------------------------------------------------------

def paginate_products(filters: ProductFilters, page: int = 1, per_page: int = 15):
    query = (
        select(Product)
        # Load category and supplier in the same query: the table shows both (no N+1).
        .options(joinedload(Product.category), joinedload(Product.supplier))
        .order_by(*SORT_OPTIONS.get(filters.sort, SORT_OPTIONS["name"]))
    )
    if filters.search:
        term = filters.search.strip()
        query = query.where(
            or_(Product.name.icontains(term, autoescape=True), Product.sku.icontains(term, autoescape=True))
        )
    if filters.category_id:
        query = query.where(Product.category_id == filters.category_id)
    if filters.stock == "low":
        query = query.where(Product.stock <= Product.min_stock)
    elif filters.stock == "out":
        query = query.where(Product.stock <= 0)
    if filters.status == "active":
        query = query.where(Product.is_active.is_(True))
    elif filters.status == "inactive":
        query = query.where(Product.is_active.is_(False))
    return db.paginate(query, page=page, per_page=per_page, error_out=False)


def low_stock_count() -> int:
    """Active products at or below their minimum stock (shown as an alert)."""
    return db.session.execute(
        select(func.count(Product.id)).where(Product.is_active.is_(True), Product.stock <= Product.min_stock)
    ).scalar_one()


def recent_movements(product: Product, limit: int = 10) -> list[StockMovement]:
    return list(
        db.session.execute(
            select(StockMovement)
            .options(joinedload(StockMovement.user))
            .where(StockMovement.product_id == product.id)
            .order_by(StockMovement.movement_date.desc(), StockMovement.id.desc())
            .limit(limit)
        ).scalars()
    )


def category_choices() -> list[tuple[int, str]]:
    return [(c.id, c.name) for c in db.session.execute(select(Category).order_by(Category.name)).scalars()]


def supplier_choices(include_id: int | None = None) -> list[tuple[int, str]]:
    """Active suppliers, plus the product's current one even if it was deactivated later."""
    query = select(Supplier).where(or_(Supplier.is_active.is_(True), Supplier.id == include_id))
    return [(s.id, s.name) for s in db.session.execute(query.order_by(Supplier.name)).scalars()]


# --- Commands ------------------------------------------------------------------------------

def create_product(data: dict, *, initial_stock: Decimal | None, user: User) -> Product:
    data = _normalize(data)
    _validate(data)
    initial_stock = initial_stock or Decimal("0")
    _validate_quantity(initial_stock, data["unit"], "El stock inicial")

    product = Product(**data, stock=Decimal("0"))
    db.session.add(product)

    if initial_stock > 0:
        # The opening balance is a ledger entry too, so the kardex adds up from day one.
        # It goes through the same function as every other movement (stock_service).
        stock_service.apply_movement(
            product,
            movement_type=MovementType.IN,
            reason=MovementReason.ADJUSTMENT,
            quantity=initial_stock,
            user=user,
            notes="Stock inicial al registrar el producto",
        )
    _commit_or_duplicate(data["sku"])  # product + movement: one transaction, all or nothing
    return product


def update_product(product: Product, data: dict) -> Product:
    data = _normalize(data)
    _validate(data, exclude_id=product.id)
    if data["unit"] != product.unit and not _fits_unit(product.stock, data["unit"]):
        raise BusinessRuleError(
            f"No puedes cambiar a una unidad entera: el stock actual ({product.stock.normalize()}) tiene decimales."
        )
    for field, value in data.items():  # "stock" is not an editable field
        setattr(product, field, value)
    _commit_or_duplicate(data["sku"])
    return product


def deactivate_product(product: Product) -> None:
    """Soft delete: hidden from lists and forms, but its history stays intact."""
    if not product.is_active:
        raise BusinessRuleError(f"El producto '{product.name}' ya está inactivo.")
    product.is_active = False
    db.session.commit()


def reactivate_product(product: Product) -> None:
    if product.is_active:
        raise BusinessRuleError(f"El producto '{product.name}' ya está activo.")
    product.is_active = True
    db.session.commit()


# --- Helpers -------------------------------------------------------------------------------

def _normalize(data: dict) -> dict:
    clean = {field: data.get(field) for field in EDITABLE_FIELDS}
    for field in ("sku", "name", "description"):
        if isinstance(clean[field], str):
            clean[field] = clean[field].strip() or None
    if clean["sku"]:
        clean["sku"] = clean["sku"].upper()
    clean["supplier_id"] = clean["supplier_id"] or None  # 0 from the select means "no supplier"
    clean["min_stock"] = clean["min_stock"] if clean["min_stock"] is not None else Decimal("0")
    return clean


def _validate(data: dict, exclude_id: int | None = None) -> None:
    if not data["sku"] or not data["name"]:
        raise BusinessRuleError("El SKU y el nombre son obligatorios.")
    if data["unit"] not in UNIT_CODES:
        raise BusinessRuleError("Unidad de medida no válida.")
    if db.session.get(Category, data["category_id"] or 0) is None:
        raise BusinessRuleError("Selecciona una categoría válida.")
    if data["supplier_id"] and db.session.get(Supplier, data["supplier_id"]) is None:
        raise BusinessRuleError("Selecciona un proveedor válido.")

    for field, label in (("purchase_price", "El precio de compra"), ("sale_price", "El precio de venta")):
        price = data[field]
        if price is None or price < 0:
            raise BusinessRuleError(f"{label} debe ser un número mayor o igual a 0.")
        if price.as_tuple().exponent < -2:
            raise BusinessRuleError(f"{label} admite como máximo 2 decimales.")
    _validate_quantity(data["min_stock"], data["unit"], "El stock mínimo")

    query = select(Product.name).where(Product.sku == data["sku"])
    if exclude_id is not None:
        query = query.where(Product.id != exclude_id)
    existing = db.session.execute(query).scalar_one_or_none()
    if existing:
        raise BusinessRuleError(f"El SKU {data['sku']} ya está asignado a '{existing}'.")


def _validate_quantity(value: Decimal, unit: str, label: str) -> None:
    if value < 0:
        raise BusinessRuleError(f"{label} no puede ser negativo.")
    if value.as_tuple().exponent < -3:
        raise BusinessRuleError(f"{label} admite como máximo 3 decimales.")
    if not _fits_unit(value, unit):
        raise BusinessRuleError(f"{label} debe ser un número entero para la unidad {unit}.")


def _fits_unit(value: Decimal, unit: str) -> bool:
    return unit in FRACTIONAL_UNITS or value == value.to_integral_value()


def _commit_or_duplicate(sku: str) -> None:
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise BusinessRuleError(f"El SKU {sku} ya está registrado.") from None
