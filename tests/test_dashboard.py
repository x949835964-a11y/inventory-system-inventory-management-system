"""Dashboard indicators, restock list and the 30-day flow series."""
import json
import re
from datetime import date, time
from decimal import Decimal

import pytest

from app.models import Category, MovementReason, MovementType
from app.services import dashboard_service, stock_service
from app.utils.dates import local_to_utc

TZ = "America/Lima"


@pytest.fixture
def shop(db, category, make_product):
    """Active products in every stock state, plus an inactive one that must be ignored."""
    tools = Category(name="Ferretería")
    db.session.add(tools)
    db.session.commit()
    return {
        "ok": make_product(sku="ARR-001", name="Arroz", stock=Decimal("50"), min_stock=Decimal("10"),
                           purchase_price=Decimal("18.50")),
        "low": make_product(sku="AZU-001", name="Azúcar", stock=Decimal("3"), min_stock=Decimal("10"),
                            purchase_price=Decimal("4.00")),
        "edge": make_product(sku="SAL-001", name="Sal", stock=Decimal("5"), min_stock=Decimal("5"),
                             purchase_price=Decimal("1.20")),
        "out": make_product(sku="ACE-001", name="Aceite", stock=Decimal("0"), min_stock=Decimal("6"),
                            purchase_price=Decimal("9.90")),
        "cable": make_product(sku="CAB-14", name="Cable", category=tools, unit="M", stock=Decimal("2.5"),
                              min_stock=Decimal("1"), purchase_price=Decimal("2.30")),
        "old": make_product(sku="VIE-001", name="Viejo", stock=Decimal("100"), min_stock=Decimal("200"),
                            purchase_price=Decimal("1.00"), is_active=False),
    }


# --- Summary ---------------------------------------------------------------------------------------

def test_summary_counts_only_active_products(shop):
    summary = dashboard_service.get_summary(TZ)
    assert summary.product_count == 5
    assert summary.low_stock_count == 3      # Azúcar, Sal (equal to minimum), Aceite
    assert summary.out_of_stock_count == 1   # Aceite


def test_inventory_value_is_stock_times_cost(shop):
    # 50*18.50 + 3*4.00 + 5*1.20 + 0*9.90 + 2.5*2.30 = 925 + 12 + 6 + 0 + 5.75
    assert dashboard_service.get_summary(TZ).inventory_value == Decimal("948.75")


def test_summary_on_an_empty_database(db):
    summary = dashboard_service.get_summary(TZ)
    assert (summary.product_count, summary.inventory_value, summary.low_stock_count) == (0, Decimal("0.00"), 0)


def test_movements_today_ignores_older_ones(db, admin, make_product):
    product = make_product(stock=Decimal("0"))
    stock_service.register_movement(product_id=product.id, movement_type=MovementType.IN,
                                    reason=MovementReason.PURCHASE, quantity=Decimal("5"), user=admin,
                                    movement_date=local_to_utc(date(2025, 1, 10), time(12), TZ))
    stock_service.register_movement(product_id=product.id, movement_type=MovementType.OUT,
                                    reason=MovementReason.SALE, quantity=Decimal("1"), user=admin)
    assert dashboard_service.get_summary(TZ).movements_today == 1


# --- Restock list ------------------------------------------------------------------------------------

def test_restock_list_puts_out_of_stock_first_then_biggest_shortfall(shop):
    names = [p.name for p in dashboard_service.restock_list()]
    # Aceite is out; then Azúcar (7 short) before Sal (0 short). Arroz, Cable and the inactive one are excluded.
    assert names == ["Aceite", "Azúcar", "Sal"]


def test_restock_list_respects_limit(shop):
    assert len(dashboard_service.restock_list(limit=2)) == 2


# --- 30-day flow ------------------------------------------------------------------------------------

@pytest.fixture
def flow(admin, make_product):
    """Movements on known 2025 dates; the series is computed as if 'today' were 15/03/2025."""
    product = make_product(stock=Decimal("0"), purchase_price=Decimal("10.00"))

    def move(movement_type, reason, qty, day, hour=12, cost=None):
        stock_service.register_movement(
            product_id=product.id, movement_type=movement_type, reason=reason, quantity=Decimal(qty),
            user=admin, unit_cost=cost, movement_date=local_to_utc(day, time(hour), TZ),
        )

    move(MovementType.IN, MovementReason.PURCHASE, "50", date(2025, 2, 1))           # outside the window
    move(MovementType.IN, MovementReason.PURCHASE, "20", date(2025, 2, 14))           # first day of the window
    move(MovementType.OUT, MovementReason.SALE, "3", date(2025, 3, 14), hour=22)      # 03:00 UTC of the 15th
    move(MovementType.OUT, MovementReason.SALE, "2", date(2025, 3, 15), hour=9)
    move(MovementType.IN, MovementReason.PURCHASE, "4", date(2025, 3, 15), hour=10, cost=Decimal("12.50"))
    return dashboard_service.daily_flow(TZ, days=30, today=date(2025, 3, 15))


def test_flow_has_one_point_per_day(flow):
    assert len(flow["labels"]) == len(flow["in_value"]) == len(flow["out_count"]) == 30
    assert (flow["labels"][0], flow["labels"][-1]) == ("14/02", "15/03")


def test_flow_groups_by_local_day(flow):
    assert flow["out_value"][-2] == 30.0   # 3 x 10.00 on the 14th (Lima), though it is the 15th in UTC
    assert flow["out_value"][-1] == 20.0   # 2 x 10.00 on the 15th
    assert flow["in_value"][-1] == 50.0    # 4 x 12.50: each movement uses its own cost
    assert (flow["in_count"][-1], flow["out_count"][-1]) == (1, 1)


def test_flow_window_boundaries_and_totals(flow):
    assert flow["in_value"][0] == 200.0             # 14/02 is inside the window
    assert flow["total_in_value"] == 250.0          # the 01/02 purchase is excluded
    assert flow["total_out_value"] == 50.0
    assert sum(flow["in_value"][1:-1]) == 0         # quiet days are zeros, not gaps


# --- Page ---------------------------------------------------------------------------------------------

def test_dashboard_page_for_employee(shop, employee, client, login):
    login("empleado", "Empleado123")
    html = client.get("/").get_data(as_text=True)
    assert "Valor del inventario" in html and "S/ 948.75" in html
    assert "Por reponer" in html and "Aceite" in html and "agotado" in html
    assert 'href="/users/"' not in html  # nothing admin-only for employees


def test_chart_data_is_embedded_as_valid_json(shop, admin, client, login):
    login("admin", "Admin123!")
    html = client.get("/").get_data(as_text=True)
    match = re.search(r'<script id="flow-data" type="application/json">(.*?)</script>', html, re.S)
    data = json.loads(match.group(1))
    assert len(data["labels"]) == 30 and set(data) >= {"in_value", "out_value", "in_count", "out_count"}
    assert "chart.umd.min.js" in html and "js/dashboard.js" in html


def test_dashboard_empty_state(db, admin, client, login):
    login("admin", "Admin123!")
    html = client.get("/").get_data(as_text=True)
    assert "Todo el stock está sobre el mínimo" in html
    assert "Aún no hay movimientos" in html
