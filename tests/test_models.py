"""Model tests: normalization, business properties and database constraints."""
import os
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.models import (
    REASONS_BY_TYPE,
    Category,
    MovementReason,
    MovementType,
    StockMovement,
    Supplier,
    User,
    UserRole,
)


# --- Application factory -------------------------------------------------------

def test_factory_uses_testing_config(app):
    assert app.config["TESTING"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


def test_factory_rejects_unknown_environment():
    with pytest.raises(ValueError):
        create_app("staging")


def test_health_endpoint_reports_database_ok(app):
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


# --- User ------------------------------------------------------------------------

def test_password_is_hashed_and_verifiable(admin):
    assert admin.password_hash != "Admin123!"
    assert admin.check_password("Admin123!")
    assert not admin.check_password("wrong-password")


def test_username_is_normalized(db):
    user = User(username="  JPerez ", full_name="Juan Pérez")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()
    assert user.username == "jperez"


def test_default_role_is_employee(db):
    user = User(username="ana", full_name="Ana Ríos")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()
    assert user.role == UserRole.EMPLOYEE
    assert not user.is_admin
    assert user.is_active


def test_admin_flag_and_role_label(admin):
    assert admin.is_admin
    assert admin.role.label == "Administrador"


# --- Category / Supplier ---------------------------------------------------------

def test_category_name_must_be_unique(db, category):
    db.session.add(Category(name="Abarrotes"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_supplier_empty_ruc_is_stored_as_null(db):
    # Two suppliers without RUC must not collide on the UNIQUE index.
    db.session.add_all([Supplier(name="Mercado A", ruc=""), Supplier(name="Mercado B", ruc="  ")])
    db.session.commit()
    assert Supplier.query.filter(Supplier.ruc.is_(None)).count() == 2


# --- Product ---------------------------------------------------------------------

def test_sku_is_normalized_to_uppercase(make_product):
    product = make_product(sku="  arr-001 ")
    assert product.sku == "ARR-001"


def test_sku_must_be_unique(db, make_product):
    make_product(sku="ARR-001")
    with pytest.raises(IntegrityError):
        make_product(sku="arr-001")


def test_invalid_unit_is_rejected(make_product):
    with pytest.raises(ValueError):
        make_product(unit="TONELADA")


def test_negative_stock_is_rejected_by_database(db, make_product):
    product = make_product()
    product.stock = Decimal("-1")
    with pytest.raises(IntegrityError):
        db.session.commit()


@pytest.mark.parametrize(
    ("stock", "min_stock", "expected"),
    [("10", "5", False), ("5", "5", True), ("2", "5", True), ("0", "0", True)],
)
def test_is_low_stock(make_product, stock, min_stock, expected):
    product = make_product(stock=Decimal(stock), min_stock=Decimal(min_stock))
    assert product.is_low_stock is expected


def test_stock_value_and_margin(make_product):
    product = make_product(stock=Decimal("4"), purchase_price=Decimal("18.50"), sale_price=Decimal("22.90"))
    assert product.stock_value == Decimal("74.00")
    assert product.margin_percent == Decimal("23.78")


def test_category_with_products_cannot_be_deleted(db, category, make_product):
    make_product()
    db.session.delete(category)
    with pytest.raises(IntegrityError):
        db.session.commit()


# --- StockMovement -----------------------------------------------------------------

def _movement(product, user, **overrides):
    data = {
        "product": product,
        "user": user,
        "movement_type": MovementType.IN,
        "reason": MovementReason.PURCHASE,
        "quantity": Decimal("5"),
        "unit_cost": Decimal("18.50"),
        "stock_before": Decimal("10"),
        "stock_after": Decimal("15"),
    }
    data.update(overrides)
    return StockMovement(**data)


def test_movement_is_saved_with_relationships(db, admin, make_product):
    product = make_product()
    movement = _movement(product, admin)
    db.session.add(movement)
    db.session.commit()

    assert movement.id is not None
    assert movement.movement_date is not None
    assert product.movements == [movement]
    assert admin.movements == [movement]
    assert movement.total_cost == Decimal("92.50")


def test_signed_quantity(db, admin, make_product):
    product = make_product()
    entry = _movement(product, admin)
    exit_ = _movement(
        product, admin, movement_type=MovementType.OUT, reason=MovementReason.SALE,
        stock_before=Decimal("15"), stock_after=Decimal("10"),
    )
    assert entry.signed_quantity == Decimal("5")
    assert exit_.signed_quantity == Decimal("-5")


def test_movement_quantity_must_be_positive(db, admin, make_product):
    db.session.add(_movement(make_product(), admin, quantity=Decimal("0")))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_product_with_movements_cannot_be_deleted(db, admin, make_product):
    product = make_product()
    db.session.add(_movement(product, admin))
    db.session.commit()

    db.session.delete(product)
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_reasons_by_type_are_consistent():
    assert MovementReason.SALE in REASONS_BY_TYPE[MovementType.OUT]
    assert MovementReason.SALE not in REASONS_BY_TYPE[MovementType.IN]
    assert MovementReason.PURCHASE not in REASONS_BY_TYPE[MovementType.OUT]
    # Adjustments are the only reason allowed in both directions.
    shared = set(REASONS_BY_TYPE[MovementType.IN]) & set(REASONS_BY_TYPE[MovementType.OUT])
    assert shared == {MovementReason.ADJUSTMENT}
