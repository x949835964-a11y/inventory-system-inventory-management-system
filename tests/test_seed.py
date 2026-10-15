"""Demo data and demo mode: the seed must respect every rule of the real system."""
from collections import defaultdict
from decimal import Decimal

import pytest

from app.demo import DEMO_ACCOUNTS
from app.models import Category, Product, StockMovement, Supplier, User
from app.seed import PRODUCTS, clear_all_data, has_data, seed_demo_data
from app.services import user_service
from app.services.exceptions import BusinessRuleError
from app.utils.peru import is_valid_ruc

SEED_DAYS = 20  # shorter history keeps the test fast; the rules are the same


@pytest.fixture
def seeded(db):
    summary = seed_demo_data(days=SEED_DAYS)
    db.session.expire_all()
    return summary


def _all(db, model):
    return db.session.execute(db.select(model)).scalars().all()


def test_seed_creates_the_demo_shop(db, seeded):
    assert seeded["users"] == len(DEMO_ACCOUNTS) == len(_all(db, User))
    assert seeded["products"] == len(PRODUCTS) == len(_all(db, Product))
    assert len(_all(db, Category)) == 8
    assert seeded["movements"] == len(_all(db, StockMovement)) > len(PRODUCTS) * 5


def test_seed_suppliers_have_valid_rucs(db, seeded):
    rucs = [s.ruc for s in _all(db, Supplier) if s.ruc]
    assert rucs and all(is_valid_ruc(ruc) for ruc in rucs)


def test_seed_ledger_is_consistent_for_every_product(db, seeded):
    """Stock = sum of movements, no negative balances, unbroken chain, chronological dates."""
    by_product = defaultdict(list)
    for movement in db.session.execute(db.select(StockMovement).order_by(StockMovement.id)).scalars():
        by_product[movement.product_id].append(movement)

    for product in _all(db, Product):
        ledger = by_product[product.id]
        assert sum((m.signed_quantity for m in ledger), Decimal("0")) == product.stock, product.sku
        assert all(m.stock_after >= 0 for m in ledger), product.sku
        for previous, current in zip(ledger, ledger[1:]):
            assert current.stock_before == previous.stock_after, product.sku
            assert current.movement_date >= previous.movement_date, product.sku


def test_seed_leaves_alerts_for_the_dashboard(seeded):
    assert seeded["low_stock"] >= 2
    assert seeded["out_of_stock"] >= 1


def test_seed_marks_discontinued_product_inactive_with_history(db, seeded):
    juice = db.session.execute(db.select(Product).filter_by(sku="JUG-1L")).scalar_one()
    assert juice.is_active is False and juice.movements


def test_demo_users_can_log_in(seeded, client, login):
    for username, _name, _role, password in DEMO_ACCOUNTS:
        response = login(username, password)
        assert response.status_code == 302 and response.headers["Location"] == "/", username
        client.post("/auth/logout")


def test_has_data_and_clear_all_data(db, seeded):
    assert has_data()
    clear_all_data()
    assert not has_data() and _all(db, StockMovement) == []


# --- CLI ---------------------------------------------------------------------------------------

def test_seed_command_refuses_to_overwrite_without_reset(app, seeded):
    result = app.test_cli_runner().invoke(args=["seed", "--days", "7"])
    assert result.exit_code != 0
    assert "--reset" in result.output


def test_seed_command_reset(app, db, seeded):
    result = app.test_cli_runner().invoke(args=["seed", "--reset", "--yes", "--days", "7"])
    assert result.exit_code == 0, result.output
    assert "Usuarios demo" in result.output and "Admin123" in result.output
    assert len(_all(db, User)) == len(DEMO_ACCOUNTS)


# --- Demo mode ------------------------------------------------------------------------------------

def test_demo_mode_shows_credentials_on_login(app, client):
    app.config["DEMO_MODE"] = True
    html = client.get("/auth/login").get_data(as_text=True)
    assert "Demo pública" in html and "Empleado123" in html


def test_no_credentials_on_login_outside_demo_mode(client):
    assert "Demo pública" not in client.get("/auth/login").get_data(as_text=True)


def test_demo_mode_protects_demo_accounts(app, seeded, db):
    app.config["DEMO_MODE"] = True
    admin = db.session.execute(db.select(User).filter_by(username="admin")).scalar_one()
    employee = db.session.execute(db.select(User).filter_by(username="empleado")).scalar_one()

    with pytest.raises(BusinessRuleError, match="demo"):
        user_service.change_own_password(admin, current_password="Admin123", new_password="Otra1234")
    with pytest.raises(BusinessRuleError, match="demo"):
        user_service.reset_password(employee, "Otra1234")
    with pytest.raises(BusinessRuleError, match="demo"):
        user_service.update_user(employee, full_name="X", role=employee.role, is_active=False, acting_user=admin)
    assert employee.is_active and admin.check_password("Admin123")


def test_demo_mode_still_allows_managing_other_users(app, seeded, db):
    app.config["DEMO_MODE"] = True
    admin = db.session.execute(db.select(User).filter_by(username="admin")).scalar_one()
    from app.models import UserRole

    visitor = user_service.create_user(username="visita", full_name="Visitante", password="Visita123", role=UserRole.EMPLOYEE)
    user_service.reset_password(visitor, "Nueva1234")
    assert visitor.check_password("Nueva1234")
    assert admin.is_admin


def test_reset_password_route_shows_demo_message(app, db, seeded, client, login):
    app.config["DEMO_MODE"] = True
    employee = db.session.execute(db.select(User).filter_by(username="empleado")).scalar_one()
    login("admin", "Admin123")
    response = client.post(f"/users/{employee.id}/password",
                           data={"new_password": "Otra1234", "confirm_password": "Otra1234"})
    assert response.status_code == 200
    assert "demo pública" in response.get_data(as_text=True)
