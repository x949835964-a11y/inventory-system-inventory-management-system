"""The ONLY place where product stock changes.

register_movement() runs as one database transaction:
  1. Lock the product row (SELECT ... FOR UPDATE) so concurrent movements queue up.
  2. Validate business rules against the fresh, locked stock.
  3. Insert the movement and update products.stock.
  4. Commit (all or nothing). Any error rolls everything back and releases the lock.
"""
from datetime import timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import func, select

from app.extensions import db
from app.models import FRACTIONAL_UNITS, REASONS_BY_TYPE, MovementReason, MovementType, Product, StockMovement, User
from app.services.exceptions import BusinessRuleError
from app.utils.dates import to_local, utc_now
from app.utils.formatters import quantity as fmt_qty

FUTURE_TOLERANCE = timedelta(minutes=5)  # small clock differences between server and client


def register_movement(
    *,
    product_id: int,
    movement_type: MovementType,
    reason: MovementReason,
    quantity: Decimal,
    user: User,
    unit_cost: Decimal | None = None,
    movement_date=None,
    notes: str | None = None,
    update_cost: bool = False,
) -> StockMovement:
    """Validate and record an entry or exit, updating stock atomically."""
    try:
        product = _lock_product(product_id)
        if product is None:
            raise BusinessRuleError("El producto no existe.")
        if not product.is_active:
            raise BusinessRuleError(f"'{product.name}' está inactivo; reactívalo para registrar movimientos.")
        if reason == MovementReason.ADJUSTMENT and not user.is_admin:
            raise BusinessRuleError("Solo un administrador puede registrar ajustes de inventario.")

        movement_date = movement_date or utc_now()
        _check_date(product, movement_date)

        if update_cost and movement_type == MovementType.IN and unit_cost is not None:
            _check_cost(unit_cost)
            product.purchase_price = unit_cost  # "last cost" policy for the product's reference price

        movement = apply_movement(
            product,
            movement_type=movement_type,
            reason=reason,
            quantity=quantity,
            user=user,
            unit_cost=unit_cost,
            movement_date=movement_date,
            notes=notes,
        )
        db.session.commit()
        return movement
    except Exception:
        db.session.rollback()
        raise


def apply_movement(
    product: Product,
    *,
    movement_type: MovementType,
    reason: MovementReason,
    quantity: Decimal,
    user: User,
    unit_cost: Decimal | None = None,
    movement_date=None,
    notes: str | None = None,
) -> StockMovement:
    """Validate quantity rules, change product.stock and add the movement. Does NOT commit.

    Also used by product_service to record the initial stock inside its own transaction.
    """
    if reason not in REASONS_BY_TYPE[movement_type]:
        raise BusinessRuleError(f"El motivo '{reason.label}' no corresponde a una {movement_type.label.lower()}.")
    _check_quantity(quantity, product)
    if unit_cost is None:
        unit_cost = product.purchase_price
    _check_cost(unit_cost)

    stock_before = product.stock
    stock_after = stock_before + quantity if movement_type == MovementType.IN else stock_before - quantity
    if stock_after < 0:
        raise BusinessRuleError(
            f"Stock insuficiente para '{product.name}': hay {fmt_qty(stock_before)} {product.unit} "
            f"y se intenta retirar {fmt_qty(quantity)} {product.unit}."
        )

    product.stock = stock_after
    movement = StockMovement(
        product=product,
        user=user,
        movement_type=movement_type,
        reason=reason,
        quantity=quantity,
        unit_cost=unit_cost,
        stock_before=stock_before,
        stock_after=stock_after,
        notes=(notes or "").strip() or None,
    )
    if movement_date is not None:
        movement.movement_date = movement_date
    db.session.add(movement)
    return movement


def _lock_product(product_id: int) -> Product | None:
    return db.session.execute(
        select(Product)
        .where(Product.id == product_id)
        # FOR UPDATE: a second transaction trying to lock this row waits until we commit.
        .with_for_update()
        # The product may already be in the session with an old stock value;
        # populate_existing overwrites it with what the locked SELECT just read.
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _check_quantity(quantity: Decimal | None, product: Product) -> None:
    if quantity is None or quantity <= 0:
        raise BusinessRuleError("La cantidad debe ser mayor que 0.")
    if quantity.as_tuple().exponent < -3:
        raise BusinessRuleError("La cantidad admite como máximo 3 decimales.")
    if product.unit not in FRACTIONAL_UNITS and quantity != quantity.to_integral_value():
        raise BusinessRuleError(f"'{product.name}' se maneja en {product.unit}: la cantidad debe ser un número entero.")


def _check_cost(unit_cost: Decimal) -> None:
    if unit_cost < 0:
        raise BusinessRuleError("El costo unitario no puede ser negativo.")
    if unit_cost.as_tuple().exponent < -2:
        raise BusinessRuleError("El costo unitario admite como máximo 2 decimales.")


def _check_date(product: Product, movement_date) -> None:
    """Keep the ledger chronological, so the kardex balance always reads top to bottom."""
    if movement_date > utc_now() + FUTURE_TOLERANCE:
        raise BusinessRuleError("No se pueden registrar movimientos con fecha futura.")
    last = db.session.execute(
        select(func.max(StockMovement.movement_date)).where(StockMovement.product_id == product.id)
    ).scalar_one()
    if last is not None and movement_date < last:
        shown = to_local(last, current_app.config["APP_TIMEZONE"]).strftime("%d/%m/%Y %H:%M")
        raise BusinessRuleError(
            f"La fecha no puede ser anterior al último movimiento de '{product.name}' ({shown})."
        )
