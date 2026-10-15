"""Shared fixtures: a fresh in-memory SQLite database for every test."""
from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import event
from sqlalchemy.engine import Engine

from app import create_app
from app.extensions import db as _db
from app.models import Category, Product, Supplier, User, UserRole


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless asked; MySQL/InnoDB always enforces them."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture
def app():
    app = create_app("testing")

    @app.before_request
    def _reset_cached_login_user():
        # The test client reuses this fixture's app context, so `g` survives between
        # requests. Flask-Login caches the user in g._login_user; clear it so every
        # request reloads the user from the session, exactly as in production.
        g.pop("_login_user", None)

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def admin(db):
    user = User(username="admin", full_name="Admin Demo", role=UserRole.ADMIN)
    user.set_password("Admin123!")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def employee(db):
    user = User(username="empleado", full_name="Empleado Demo", role=UserRole.EMPLOYEE)
    user.set_password("Empleado123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    """login("admin", "Admin123!") posts the login form and returns the response."""

    def _login(username, password, next_url=None, follow_redirects=False):
        url = "/auth/login" + (f"?next={next_url}" if next_url else "")
        return client.post(
            url,
            data={"username": username, "password": password},
            follow_redirects=follow_redirects,
        )

    return _login


@pytest.fixture
def category(db):
    category = Category(name="Abarrotes")
    db.session.add(category)
    db.session.commit()
    return category


@pytest.fixture
def supplier(db):
    supplier = Supplier(name="Distribuidora Lima SAC", ruc="20600123450")  # valid check digit
    db.session.add(supplier)
    db.session.commit()
    return supplier


@pytest.fixture
def make_product(db, category):
    """Factory: make_product(sku="X", stock=Decimal("5")) with sensible defaults."""

    def _make(**overrides):
        data = {
            "sku": "ARR-001",
            "name": "Arroz extra 5 kg",
            "category": category,
            "purchase_price": Decimal("18.50"),
            "sale_price": Decimal("22.90"),
            "unit": "UND",
            "stock": Decimal("10"),
            "min_stock": Decimal("5"),
        }
        data.update(overrides)
        product = Product(**data)
        db.session.add(product)
        db.session.commit()
        return product

    return _make
