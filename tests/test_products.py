"""Products: SKU, prices and units, initial stock, search/filters, soft delete and permissions."""
from decimal import Decimal

import pytest

from app.models import MovementReason, MovementType, Product, StockMovement, Supplier
from app.services import product_service
from app.services.exceptions import BusinessRuleError
from app.services.product_service import ProductFilters


@pytest.fixture
def product_data(category):
    """Valid data, as the form would deliver it to the service."""

    def _data(**overrides):
        data = {
            "sku": "  lec-001 ",
            "name": "Leche evaporada 400 g",
            "description": "",
            "category_id": category.id,
            "supplier_id": 0,
            "purchase_price": Decimal("3.20"),
            "sale_price": Decimal("3.80"),
            "unit": "UND",
            "min_stock": Decimal("12"),
        }
        data.update(overrides)
        return data

    return _data


def _movements(db, product):
    return db.session.execute(db.select(StockMovement).filter_by(product_id=product.id)).scalars().all()


# --- Create --------------------------------------------------------------------------------

def test_create_normalizes_and_starts_without_stock(db, admin, product_data):
    product = product_service.create_product(product_data(), initial_stock=None, user=admin)
    assert product.sku == "LEC-001"
    assert product.supplier_id is None  # 0 from the select = "no supplier"
    assert product.description is None
    assert product.stock == 0
    assert _movements(db, product) == []


def test_initial_stock_is_recorded_as_a_movement(db, admin, product_data):
    product = product_service.create_product(product_data(), initial_stock=Decimal("24"), user=admin)

    assert product.stock == Decimal("24")
    [movement] = _movements(db, product)
    assert movement.movement_type == MovementType.IN
    assert movement.reason == MovementReason.ADJUSTMENT
    assert (movement.stock_before, movement.stock_after) == (Decimal("0"), Decimal("24"))
    assert movement.unit_cost == Decimal("3.20")
    assert movement.user_id == admin.id


def test_sku_must_be_unique_ignoring_case(admin, product_data, make_product):
    make_product(sku="LEC-001", name="Leche original")
    with pytest.raises(BusinessRuleError, match="ya está asignado a 'Leche original'"):
        product_service.create_product(product_data(sku="lec-001"), initial_stock=None, user=admin)


@pytest.mark.parametrize(
    ("overrides", "initial", "message"),
    [
        ({"min_stock": Decimal("2.5")}, None, "entero"),            # UND can't be fractional
        ({}, Decimal("1.5"), "entero"),
        ({"purchase_price": Decimal("3.205")}, None, "2 decimales"),
        ({"sale_price": Decimal("-1")}, None, "mayor o igual a 0"),
        ({"unit": "TON"}, None, "Unidad"),
        ({"category_id": 9999}, None, "categoría"),
        ({"supplier_id": 9999}, None, "proveedor"),
        ({"name": "   "}, None, "obligatorios"),
    ],
)
def test_create_rejects_invalid_data(admin, product_data, overrides, initial, message):
    with pytest.raises(BusinessRuleError, match=message):
        product_service.create_product(product_data(**overrides), initial_stock=initial, user=admin)


def test_fractional_units_accept_decimals(admin, product_data):
    product = product_service.create_product(
        product_data(sku="CAB-14", name="Cable mellizo N.º 14", unit="M", min_stock=Decimal("10.5")),
        initial_stock=Decimal("100.250"),
        user=admin,
    )
    assert product.stock == Decimal("100.250")
    assert product.allows_fractions


# --- Update --------------------------------------------------------------------------------

def test_update_never_touches_stock(make_product, product_data):
    product = make_product(sku="LEC-001", stock=Decimal("10"))
    product_service.update_product(product, product_data(name="Leche evaporada 410 g", stock=Decimal("999")))
    assert product.name == "Leche evaporada 410 g"
    assert product.stock == Decimal("10")


def test_update_can_keep_its_own_sku(make_product, product_data):
    product = make_product(sku="LEC-001")
    product_service.update_product(product, product_data(sku="lec-001"))
    assert product.sku == "LEC-001"


def test_cannot_switch_to_whole_unit_with_fractional_stock(make_product, product_data):
    product = make_product(sku="QUE-01", unit="KG", stock=Decimal("2.500"), min_stock=Decimal("1"))
    with pytest.raises(BusinessRuleError, match="unidad entera"):
        product_service.update_product(product, product_data(sku="QUE-01", unit="UND", min_stock=Decimal("1")))
    assert product.unit == "KG"


# --- Queries ---------------------------------------------------------------------------------

@pytest.fixture
def catalog(db, category, make_product):
    """Four products covering every stock state, plus one inactive."""
    from app.models import Category

    tools = Category(name="Ferretería")
    db.session.add(tools)
    db.session.commit()
    return {
        "ok": make_product(sku="ARR-001", name="Arroz extra", stock=Decimal("50"), min_stock=Decimal("10")),
        "low": make_product(sku="AZU-001", name="Azúcar rubia", stock=Decimal("3"), min_stock=Decimal("10")),
        "out": make_product(sku="ACE-001", name="Aceite vegetal", stock=Decimal("0"), min_stock=Decimal("5")),
        "tool": make_product(sku="MAR-001", name="Martillo", category=tools, stock=Decimal("8"), min_stock=Decimal("2")),
        "old": make_product(sku="VIE-001", name="Producto viejo", stock=Decimal("0"), is_active=False),
    }


def _names(filters, **kw):
    return [p.name for p in product_service.paginate_products(filters, **kw).items]


def test_default_list_shows_only_active_products_by_name(catalog):
    assert _names(ProductFilters()) == ["Aceite vegetal", "Arroz extra", "Azúcar rubia", "Martillo"]


def test_search_by_name_or_sku(catalog):
    assert _names(ProductFilters(search="arroz")) == ["Arroz extra"]
    assert _names(ProductFilters(search="mar-0")) == ["Martillo"]


def test_filter_by_category(catalog):
    assert _names(ProductFilters(category_id=catalog["tool"].category_id)) == ["Martillo"]


def test_low_stock_and_out_of_stock_filters(catalog):
    assert _names(ProductFilters(stock="low")) == ["Aceite vegetal", "Azúcar rubia"]
    assert _names(ProductFilters(stock="out")) == ["Aceite vegetal"]


def test_status_filter_and_sort(catalog):
    assert _names(ProductFilters(status="inactive")) == ["Producto viejo"]
    assert len(_names(ProductFilters(status="all"))) == 5
    assert _names(ProductFilters(sort="stock"))[0] == "Aceite vegetal"


def test_pagination(catalog):
    first = product_service.paginate_products(ProductFilters(), page=1, per_page=3)
    second = product_service.paginate_products(ProductFilters(), page=2, per_page=3)
    assert (first.total, first.pages, len(first.items), len(second.items)) == (4, 2, 3, 1)


def test_low_stock_count_ignores_inactive_products(catalog):
    assert product_service.low_stock_count() == 2


def test_inactive_supplier_only_listed_for_its_own_products(db, supplier):
    old = Supplier(name="Proveedor antiguo", is_active=False)
    db.session.add(old)
    db.session.commit()
    assert [name for _, name in product_service.supplier_choices()] == ["Distribuidora Lima SAC"]
    assert len(product_service.supplier_choices(include_id=old.id)) == 2


# --- Soft delete -------------------------------------------------------------------------------

def test_deactivate_keeps_history(db, admin, product_data):
    product = product_service.create_product(product_data(), initial_stock=Decimal("5"), user=admin)
    product_service.deactivate_product(product)

    assert db.session.get(Product, product.id).is_active is False  # still in the database
    assert len(_movements(db, product)) == 1
    with pytest.raises(BusinessRuleError, match="ya está inactivo"):
        product_service.deactivate_product(product)

    product_service.reactivate_product(product)
    assert product.is_active


# --- Routes and permissions ------------------------------------------------------------------

def _form(category, **overrides):
    data = {
        "sku": "lec-001", "name": "Leche evaporada", "description": "", "category_id": category.id,
        "supplier_id": 0, "unit": "UND", "purchase_price": "3,20", "sale_price": "3,80",
        "min_stock": "12", "initial_stock": "24",
    }
    data.update(overrides)
    return data


def test_employee_creates_product_with_comma_decimals(db, employee, category, client, login):
    login("empleado", "Empleado123")
    response = client.post("/products/new", data=_form(category))
    assert response.status_code == 302

    product = db.session.execute(db.select(Product).filter_by(sku="LEC-001")).scalar_one()
    assert response.headers["Location"] == f"/products/{product.id}"
    assert product.purchase_price == Decimal("3.20")
    assert product.stock == Decimal("24")


def test_form_shows_spanish_validation_errors(admin, category, client, login):
    login("admin", "Admin123!")
    response = client.post("/products/new", data=_form(category, purchase_price="3,205", category_id=0))
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Máximo 2 decimales" in html
    assert "Selecciona una categoría" in html


def test_selling_below_cost_is_allowed_with_a_warning(admin, category, client, login):
    login("admin", "Admin123!")
    response = client.post("/products/new", data=_form(category, sale_price="2,50"), follow_redirects=True)
    assert "menor que el precio de compra" in response.get_data(as_text=True)


def test_list_shows_stock_indicators(catalog, admin, client, login):
    login("admin", "Admin123!")
    html = client.get("/products/").get_data(as_text=True)
    assert "Agotado" in html and "Stock bajo" in html and "Disponible" in html
    assert "Producto viejo" not in html


def test_edit_form_has_no_stock_field(make_product, admin, client, login):
    product = make_product()
    login("admin", "Admin123!")
    html = client.get(f"/products/{product.id}/edit").get_data(as_text=True)
    assert 'name="stock"' not in html and 'name="initial_stock"' not in html
    assert "Cambia solo con movimientos" in html


def test_employee_cannot_deactivate_or_see_inactive_products(catalog, employee, client, login):
    login("empleado", "Empleado123")
    active, old = catalog["ok"], catalog["old"]
    assert client.post(f"/products/{active.id}/deactivate").status_code == 403
    assert client.post(f"/products/{old.id}/activate").status_code == 403
    assert client.get(f"/products/{old.id}").status_code == 404
    assert "Producto viejo" not in client.get("/products/?status=all").get_data(as_text=True)
    assert active.is_active


def test_admin_deactivates_and_reactivates(catalog, admin, client, login):
    login("admin", "Admin123!")
    product = catalog["ok"]
    assert client.post(f"/products/{product.id}/deactivate").status_code == 302
    assert product.is_active is False
    assert client.get(f"/products/{product.id}/edit").status_code == 302  # must reactivate first
    assert client.post(f"/products/{product.id}/activate").status_code == 302
    assert product.is_active is True


def test_detail_page_shows_initial_movement(db, admin, category, client, login):
    login("admin", "Admin123!")
    client.post("/products/new", data=_form(category))
    product = db.session.execute(db.select(Product).filter_by(sku="LEC-001")).scalar_one()
    html = client.get(f"/products/{product.id}").get_data(as_text=True)
    assert "Ajuste de inventario" in html and "Valor en inventario" in html
