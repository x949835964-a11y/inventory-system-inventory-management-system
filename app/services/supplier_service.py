"""Supplier rules: valid and unique RUC, referential integrity with products."""
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Product, Supplier
from app.services.exceptions import BusinessRuleError
from app.utils.peru import ruc_problem

STATUS_FILTERS = {"active": True, "inactive": False}  # anything else = all


def paginate_suppliers(*, search: str = "", status: str = "active", page: int = 1, per_page: int = 15):
    """Return (pagination, {supplier_id: product_count}) for the current page."""
    query = select(Supplier).order_by(Supplier.name)
    if search:
        query = query.where(
            or_(
                Supplier.name.icontains(search, autoescape=True),
                Supplier.ruc.icontains(search, autoescape=True),
                Supplier.contact_name.icontains(search, autoescape=True),
            )
        )
    if status in STATUS_FILTERS:
        query = query.where(Supplier.is_active.is_(STATUS_FILTERS[status]))
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return pagination, product_counts([s.id for s in pagination.items])


def product_counts(supplier_ids: list[int]) -> dict[int, int]:
    if not supplier_ids:
        return {}
    rows = db.session.execute(
        select(Product.supplier_id, func.count(Product.id))
        .where(Product.supplier_id.in_(supplier_ids))
        .group_by(Product.supplier_id)
    )
    return dict(rows.all())


def create_supplier(**data) -> Supplier:
    data = _normalize(data)
    _validate(data)
    supplier = Supplier(**data)
    db.session.add(supplier)
    _commit_or_duplicate(data.get("ruc"))
    return supplier


def update_supplier(supplier: Supplier, **data) -> Supplier:
    data = _normalize(data)
    _validate(data, exclude_id=supplier.id)
    for field, value in data.items():
        setattr(supplier, field, value)
    _commit_or_duplicate(data.get("ruc"))
    return supplier


def delete_supplier(supplier: Supplier) -> None:
    count = product_counts([supplier.id]).get(supplier.id, 0)
    if count:
        raise BusinessRuleError(
            f"No se puede eliminar '{supplier.name}': abastece {count} producto(s). "
            "Puedes desactivarlo para que no aparezca en los formularios."
        )
    db.session.delete(supplier)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise BusinessRuleError(f"No se puede eliminar '{supplier.name}': tiene productos asociados.") from None


EDITABLE_FIELDS = ("name", "ruc", "phone", "email", "address", "contact_name", "is_active")


def _normalize(data: dict) -> dict:
    """Keep only editable fields; trim text and turn empty strings into None."""
    clean = {}
    for field in EDITABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if isinstance(value, str):
            value = value.strip() or None
        clean[field] = value
    if clean.get("ruc"):
        clean["ruc"] = clean["ruc"].replace(" ", "")
    if clean.get("email"):
        clean["email"] = clean["email"].lower()
    return clean


def _validate(data: dict, exclude_id: int | None = None) -> None:
    if not data.get("name"):
        raise BusinessRuleError("El nombre del proveedor es obligatorio.")
    ruc = data.get("ruc")
    if ruc is None:
        return
    # Validated here too, not only in the form: the service is the single source of truth.
    problem = ruc_problem(ruc)
    if problem:
        raise BusinessRuleError(problem)
    query = select(Supplier.name).where(Supplier.ruc == ruc)
    if exclude_id is not None:
        query = query.where(Supplier.id != exclude_id)
    existing = db.session.execute(query).scalar_one_or_none()
    if existing:
        raise BusinessRuleError(f"El RUC {ruc} ya está registrado para '{existing}'.")


def _commit_or_duplicate(ruc: str | None) -> None:
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise BusinessRuleError(f"El RUC {ruc} ya está registrado.") from None
