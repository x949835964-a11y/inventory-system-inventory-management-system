"""Category rules: unique names and referential integrity with products."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Category, Product
from app.services.exceptions import BusinessRuleError


def paginate_categories(*, search: str = "", page: int = 1, per_page: int = 15):
    """Return (pagination, {category_id: product_count}) for the current page."""
    query = select(Category).order_by(Category.name)
    if search:
        # autoescape: a user typing "%" or "_" searches for that character, not a wildcard.
        query = query.where(Category.name.icontains(search, autoescape=True))
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return pagination, product_counts([c.id for c in pagination.items])


def product_counts(category_ids: list[int]) -> dict[int, int]:
    """Count products per category with ONE grouped query (avoids N+1 queries in the list)."""
    if not category_ids:
        return {}
    rows = db.session.execute(
        select(Product.category_id, func.count(Product.id))
        .where(Product.category_id.in_(category_ids))
        .group_by(Product.category_id)
    )
    return dict(rows.all())


def create_category(*, name: str, description: str | None) -> Category:
    name = name.strip()
    _ensure_name_available(name)
    category = Category(name=name, description=_clean(description))
    db.session.add(category)
    _commit_or_duplicate(name)
    return category


def update_category(category: Category, *, name: str, description: str | None) -> Category:
    name = name.strip()
    _ensure_name_available(name, exclude_id=category.id)
    category.name = name
    category.description = _clean(description)
    _commit_or_duplicate(name)
    return category


def delete_category(category: Category) -> None:
    count = product_counts([category.id]).get(category.id, 0)
    if count:
        raise BusinessRuleError(
            f"No se puede eliminar '{category.name}': tiene {count} producto(s) asociado(s). "
            "Reasígnalos a otra categoría primero."
        )
    db.session.delete(category)
    try:
        db.session.commit()
    except IntegrityError:
        # A product was assigned between the check and the delete: the FK (RESTRICT) protects us.
        db.session.rollback()
        raise BusinessRuleError(f"No se puede eliminar '{category.name}': tiene productos asociados.") from None


def _ensure_name_available(name: str, exclude_id: int | None = None) -> None:
    # Case-insensitive: "Bebidas" and "bebidas" are the same category.
    query = select(Category.id).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if db.session.execute(query).first():
        raise BusinessRuleError(f"Ya existe una categoría llamada '{name}'.")


def _commit_or_duplicate(name: str) -> None:
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise BusinessRuleError(f"Ya existe una categoría llamada '{name}'.") from None


def _clean(text: str | None) -> str | None:
    text = (text or "").strip()
    return text or None
