"""Kardex calculations, movement screens and their permissions."""
from datetime import date, time
from decimal import Decimal

import pytest

from app.models import MovementReason, MovementType, Product
from app.services import kardex_service, stock_service
from app.utils.dates import local_to_utc, local_today

TZ = "America/Lima"
IN, OUT = MovementType.IN, MovementType.OUT


def lima(y, m, d, h=12, mi=0):
    """A Lima wall-clock moment, stored as naive UTC like the app does."""
    return local_to_utc(date(y, m, d), time(h, mi), TZ)


def _register(product, user, movement_type, reason, qty, when):
    return stock_service.register_movement(
        product_id=product.id, movement_type=movement_type, reason=reason,
        quantity=Decimal(str(qty)), user=user, movement_date=when,
    )


@pytest.fixture
def ledger(admin, make_product):
    """A product with movements on known dates in 2025 (always in the past)."""
    product = make_product(sku="KAR-001", name="Detergente 1 kg", stock=Decimal("0"), min_stock=Decimal("5"))
    _register(product, admin, IN, MovementReason.PURCHASE, 20, lima(2025, 3, 1))
    _register(product, admin, OUT, MovementReason.SALE, 5, lima(2025, 3, 10))
    _register(product, admin, OUT, MovementReason.SALE, 3, lima(2025, 3, 14, 22, 0))  # 03:00 UTC of the 15th
    _register(product, admin, IN, MovementReason.PURCHASE, 10, lima(2025, 3, 15, 9, 0))
    return product


# --- Kardex service -------------------------------------------------------------------------------

def test_kardex_opening_balance_and_totals(ledger):
    kardex = kardex_service.build_kardex(ledger, date(2025, 3, 10), date(2025, 3, 14), TZ)
    assert kardex.opening_balance == Decimal("20")
    assert [m.quantity for m in kardex.rows] == [Decimal("5"), Decimal("3")]
    assert (kardex.total_in, kardex.total_out, kardex.closing_balance) == (0, Decimal("8"), Decimal("12"))
    assert kardex.is_consistent


def test_kardex_uses_local_days_not_utc_days(ledger):
    """The 22:00 sale on Lima's 14th is 03:00 UTC on the 15th: it must belong to the 14th."""
    day_14 = kardex_service.build_kardex(ledger, date(2025, 3, 14), date(2025, 3, 14), TZ)
    day_15 = kardex_service.build_kardex(ledger, date(2025, 3, 15), date(2025, 3, 15), TZ)
    assert [m.quantity for m in day_14.rows] == [Decimal("3")]
    assert [m.quantity for m in day_15.rows] == [Decimal("10")]
    assert day_15.opening_balance == Decimal("12")


def test_kardex_full_range_matches_current_stock(db, ledger):
    kardex = kardex_service.build_kardex(ledger, date(2025, 1, 1), date(2025, 12, 31), TZ)
    assert kardex.opening_balance == 0
    assert kardex.closing_balance == db.session.get(Product, ledger.id).stock == Decimal("22")
    assert kardex.total_in_cost == Decimal("555.00")  # 30 units x 18.50


def test_kardex_with_reversed_dates_is_fixed(ledger):
    kardex = kardex_service.build_kardex(ledger, date(2025, 3, 31), date(2025, 3, 1), TZ)
    assert kardex.date_from < kardex.date_to and len(kardex.rows) == 4


def test_kardex_period_without_movements_keeps_balance(ledger):
    kardex = kardex_service.build_kardex(ledger, date(2025, 6, 1), date(2025, 6, 30), TZ)
    assert kardex.rows == [] and kardex.opening_balance == kardex.closing_balance == Decimal("22")


# --- Routes ------------------------------------------------------------------------------------

def _today():
    return local_today(TZ).isoformat()


def _exit_form(product, **overrides):
    data = {"product_id": product.id, "reason": "sale", "quantity": "3", "movement_date": _today(), "notes": ""}
    data.update(overrides)
    return data


def test_employee_registers_a_sale(db, employee, make_product, client, login):
    product = make_product(stock=Decimal("10"))
    login("empleado", "Empleado123")
    response = client.post("/movements/new/out", data=_exit_form(product))
    assert response.status_code == 302
    assert response.headers["Location"] == f"/products/{product.id}"
    db.session.expire_all()
    assert db.session.get(Product, product.id).stock == Decimal("7")


def test_sale_leaving_low_stock_warns(employee, make_product, client, login):
    product = make_product(stock=Decimal("10"), min_stock=Decimal("5"))
    login("empleado", "Empleado123")
    response = client.post("/movements/new/out", data=_exit_form(product, quantity="6"), follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "Salida registrada" in html and "Conviene reponer" in html


def test_insufficient_stock_shows_a_clear_error(db, employee, make_product, client, login):
    product = make_product(stock=Decimal("2"))
    login("empleado", "Empleado123")
    response = client.post("/movements/new/out", data=_exit_form(product, quantity="5"))
    assert response.status_code == 200
    assert "Stock insuficiente" in response.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Product, product.id).stock == Decimal("2")


def test_entry_with_new_cost(db, employee, make_product, client, login):
    product = make_product(stock=Decimal("0"), purchase_price=Decimal("18.50"))
    login("empleado", "Empleado123")
    response = client.post("/movements/new/in", data={
        "product_id": product.id, "reason": "purchase", "quantity": "12", "movement_date": _today(),
        "unit_cost": "19,90", "update_cost": "y", "notes": "Factura F001-123",
    })
    assert response.status_code == 302
    db.session.expire_all()
    product = db.session.get(Product, product.id)
    assert (product.stock, product.purchase_price) == (Decimal("12"), Decimal("19.90"))


def test_future_date_is_rejected_by_the_form(employee, make_product, client, login):
    product = make_product()
    login("empleado", "Empleado123")
    response = client.post("/movements/new/out", data=_exit_form(product, movement_date="2999-01-01"))
    assert "La fecha no puede ser futura" in response.get_data(as_text=True)


def test_adjustment_is_offered_only_to_admins(admin, employee, app, make_product):
    product = make_product()
    admin_client, employee_client = app.test_client(), app.test_client()
    admin_client.post("/auth/login", data={"username": "admin", "password": "Admin123!"})
    employee_client.post("/auth/login", data={"username": "empleado", "password": "Empleado123"})

    assert 'value="adjustment"' in admin_client.get("/movements/new/out").get_data(as_text=True)
    assert 'value="adjustment"' not in employee_client.get("/movements/new/out").get_data(as_text=True)

    # Even forcing the value in the POST, the employee can't do it.
    response = employee_client.post("/movements/new/out", data=_exit_form(product, reason="adjustment"))
    assert response.status_code == 200
    assert product.stock == Decimal("10")


def test_product_is_preselected_from_the_url(employee, make_product, client, login):
    product = make_product()
    login("empleado", "Empleado123")
    html = client.get(f"/movements/new/in?product_id={product.id}").get_data(as_text=True)
    assert f'<option selected value="{product.id}">' in html or f'value="{product.id}" selected' in html


def test_unknown_movement_type_is_404(employee, client, login):
    login("empleado", "Empleado123")
    assert client.get("/movements/new/transfer").status_code == 404


def test_movement_list_filters_by_type(ledger, admin, client, login):
    login("admin", "Admin123!")
    html = client.get("/movements/?type=out").get_data(as_text=True)
    assert "2 movimiento(s)" in html
    html = client.get("/movements/?type=in&q=kar-001").get_data(as_text=True)
    assert "2 movimiento(s)" in html


def test_movement_list_filters_by_local_dates(ledger, admin, client, login):
    login("admin", "Admin123!")
    html = client.get("/movements/?from=2025-03-14&to=2025-03-14").get_data(as_text=True)
    assert "1 movimiento(s)" in html


def test_kardex_page(ledger, employee, client, login):
    login("empleado", "Empleado123")
    response = client.get(f"/movements/kardex/{ledger.id}?from=2025-03-01&to=2025-03-31")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Saldo inicial" in html and "Totales del periodo" in html and "Inconsistencia" not in html


def test_kardex_ignores_invalid_dates(ledger, employee, client, login):
    login("empleado", "Empleado123")
    assert client.get(f"/movements/kardex/{ledger.id}?from=ayer&to=2025-13-45").status_code == 200
