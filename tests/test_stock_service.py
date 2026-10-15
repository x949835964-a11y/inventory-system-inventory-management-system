"""The heart of the system: stock only changes through validated, atomic movements."""
import os
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.models import MovementReason, MovementType, Product, StockMovement, User
from app.services import stock_service
from app.services.exceptions import BusinessRuleError
from app.utils.dates import utc_now

IN, OUT = MovementType.IN, MovementType.OUT


def register(product, user, movement_type, reason, quantity, **kwargs):
    return stock_service.register_movement(
        product_id=product.id,
        movement_type=movement_type,
        reason=reason,
        quantity=Decimal(str(quantity)),
        user=user,
        **kwargs,
    )


def movements_of(db, product):
    return db.session.execute(
        db.select(StockMovement).filter_by(product_id=product.id).order_by(StockMovement.id)
    ).scalars().all()


def fresh_stock(db, product):
    db.session.expire_all()
    return db.session.get(Product, product.id).stock


# --- Happy paths ------------------------------------------------------------------------------

def test_entry_increases_stock_and_records_snapshot(db, employee, make_product):
    product = make_product(stock=Decimal("10"))
    movement = register(product, employee, IN, MovementReason.PURCHASE, 15)

    assert fresh_stock(db, product) == Decimal("25")
    assert (movement.stock_before, movement.stock_after) == (Decimal("10"), Decimal("25"))
    assert movement.user_id == employee.id
    assert movement.unit_cost == Decimal("18.50")  # defaults to the product's purchase price


def test_exit_decreases_stock(db, employee, make_product):
    product = make_product(stock=Decimal("10"))
    register(product, employee, OUT, MovementReason.SALE, 4)
    assert fresh_stock(db, product) == Decimal("6")


def test_exit_can_leave_stock_at_exactly_zero(db, employee, make_product):
    product = make_product(stock=Decimal("10"))
    register(product, employee, OUT, MovementReason.SHRINKAGE, 10, notes="Lote vencido")
    assert fresh_stock(db, product) == Decimal("0")
    assert movements_of(db, product)[0].notes == "Lote vencido"


def test_fractional_units_accept_decimals(db, employee, make_product):
    product = make_product(unit="M", stock=Decimal("100"))
    register(product, employee, OUT, MovementReason.SALE, "2.5")
    assert fresh_stock(db, product) == Decimal("97.5")


def test_purchase_can_update_reference_cost(db, employee, make_product):
    product = make_product(purchase_price=Decimal("18.50"))
    movement = register(product, employee, IN, MovementReason.PURCHASE, 5,
                        unit_cost=Decimal("19.90"), update_cost=True)
    assert movement.unit_cost == Decimal("19.90")
    db.session.expire_all()
    assert db.session.get(Product, product.id).purchase_price == Decimal("19.90")


def test_purchase_cost_without_update_keeps_reference_price(db, employee, make_product):
    product = make_product(purchase_price=Decimal("18.50"))
    register(product, employee, IN, MovementReason.PURCHASE, 5, unit_cost=Decimal("17.00"))
    db.session.expire_all()
    assert db.session.get(Product, product.id).purchase_price == Decimal("18.50")


# --- Business rules -------------------------------------------------------------------------------

def test_cannot_sell_more_than_available(db, employee, make_product):
    product = make_product(stock=Decimal("3"))
    with pytest.raises(BusinessRuleError, match="Stock insuficiente.*hay 3 UND.*retirar 5 UND"):
        register(product, employee, OUT, MovementReason.SALE, 5)
    assert fresh_stock(db, product) == Decimal("3")
    assert movements_of(db, product) == []


@pytest.mark.parametrize(
    ("quantity", "message"),
    [(0, "mayor que 0"), (-2, "mayor que 0"), ("1.5", "número entero"), ("0.0001", "3 decimales")],
)
def test_invalid_quantities(db, employee, make_product, quantity, message):
    product = make_product(stock=Decimal("10"))
    with pytest.raises(BusinessRuleError, match=message):
        register(product, employee, IN, MovementReason.PURCHASE, quantity)
    assert fresh_stock(db, product) == Decimal("10")


def test_reason_must_match_direction(employee, make_product):
    product = make_product()
    with pytest.raises(BusinessRuleError, match="no corresponde"):
        register(product, employee, IN, MovementReason.SALE, 1)


def test_only_admins_register_adjustments(db, admin, employee, make_product):
    product = make_product(stock=Decimal("10"))
    with pytest.raises(BusinessRuleError, match="administrador"):
        register(product, employee, OUT, MovementReason.ADJUSTMENT, 1)
    register(product, admin, OUT, MovementReason.ADJUSTMENT, 1, notes="Conteo físico")
    assert fresh_stock(db, product) == Decimal("9")


def test_inactive_products_reject_movements(employee, make_product):
    product = make_product(is_active=False)
    with pytest.raises(BusinessRuleError, match="inactivo"):
        register(product, employee, IN, MovementReason.PURCHASE, 1)


def test_unknown_product(employee):
    with pytest.raises(BusinessRuleError, match="no existe"):
        stock_service.register_movement(
            product_id=999, movement_type=IN, reason=MovementReason.PURCHASE, quantity=Decimal("1"), user=employee
        )


def test_future_dates_are_rejected(employee, make_product):
    product = make_product()
    with pytest.raises(BusinessRuleError, match="futura"):
        register(product, employee, IN, MovementReason.PURCHASE, 1, movement_date=utc_now() + timedelta(days=1))


def test_cannot_backdate_before_the_last_movement(db, employee, make_product):
    product = make_product(stock=Decimal("10"))
    register(product, employee, OUT, MovementReason.SALE, 1)
    with pytest.raises(BusinessRuleError, match="anterior al último movimiento"):
        register(product, employee, IN, MovementReason.PURCHASE, 1, movement_date=utc_now() - timedelta(days=1))
    assert fresh_stock(db, product) == Decimal("9")


def test_ledger_always_adds_up(db, admin, make_product):
    """Replaying the ledger must reproduce the stored stock (the kardex invariant)."""
    product = make_product(stock=Decimal("0"))
    steps = [(IN, MovementReason.PURCHASE, 20), (OUT, MovementReason.SALE, 7),
             (OUT, MovementReason.SHRINKAGE, 1), (IN, MovementReason.CUSTOMER_RETURN, 2),
             (OUT, MovementReason.ADJUSTMENT, 4)]
    for movement_type, reason, qty in steps:
        register(product, admin, movement_type, reason, qty)

    ledger = movements_of(db, product)
    replayed = sum((m.signed_quantity for m in ledger), Decimal("0"))
    assert replayed == fresh_stock(db, product) == Decimal("10")
    for previous, current in zip(ledger, ledger[1:]):
        assert current.stock_before == previous.stock_after  # no gaps in the chain


# --- Transactions and locking ------------------------------------------------------------------------

def test_failed_commit_leaves_no_trace(db, employee, make_product, monkeypatch):
    product = make_product(stock=Decimal("10"))

    def database_down():
        raise RuntimeError("Se perdió la conexión con la base de datos")

    # Patch the real Session behind the scoped_session proxy (the one the service will use).
    monkeypatch.setattr(db.session(), "commit", database_down)
    with pytest.raises(RuntimeError):
        register(product, employee, OUT, MovementReason.SALE, 4)
    monkeypatch.undo()

    assert fresh_stock(db, product) == Decimal("10")  # rolled back: all or nothing
    assert movements_of(db, product) == []


def test_lock_rereads_stock_instead_of_trusting_the_session(db, employee, make_product):
    """Another process sold 8 units; our in-memory object still says 10.
    populate_existing makes the locked SELECT overwrite the stale value."""
    product = make_product(stock=Decimal("10"))
    db.session.execute(
        update(Product).where(Product.id == product.id).values(stock=Decimal("2"))
        .execution_options(synchronize_session=False)
    )
    assert product.stock == Decimal("10")  # stale copy

    with pytest.raises(BusinessRuleError, match="hay 2 UND"):
        register(product, employee, OUT, MovementReason.SALE, 5)


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("mysql"),
    reason="Requiere MySQL (TEST_DATABASE_URL): SQLite no implementa SELECT ... FOR UPDATE.",
)
def test_two_cashiers_cannot_sell_the_last_unit_twice(app, db, admin, make_product):
    product = make_product(stock=Decimal("1"), min_stock=Decimal("0"))
    product_id, admin_id = product.id, admin.id
    start_together = threading.Barrier(2)
    results = []

    def cashier():
        with app.app_context():  # own context = own session and DB connection
            try:
                user = db.session.get(User, admin_id)
                start_together.wait()
                stock_service.register_movement(
                    product_id=product_id, movement_type=OUT, reason=MovementReason.SALE,
                    quantity=Decimal("1"), user=user,
                )
                results.append("sold")
            except BusinessRuleError:
                results.append("rejected")
            finally:
                db.session.remove()

    threads = [threading.Thread(target=cashier) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    # Without the row lock both would read stock=1 and both sales would "succeed".
    assert sorted(results) == ["rejected", "sold"]
    assert fresh_stock(db, product) == Decimal("0")
    assert len(movements_of(db, product)) == 1
