"""Categories and suppliers: RUC validation, uniqueness, permissions and referential integrity."""
import pytest

from app.models import Category, Supplier
from app.services import category_service, supplier_service
from app.services.exceptions import BusinessRuleError
from app.utils.peru import is_valid_ruc, ruc_problem

SUNAT_RUC = "20131312955"  # SUNAT's own RUC, a real-world valid example


def _get(db, model, **filters):
    return db.session.execute(db.select(model).filter_by(**filters)).scalar_one_or_none()


# --- RUC validation ----------------------------------------------------------------------

@pytest.mark.parametrize("ruc", [SUNAT_RUC, "20600123450", "10456789019", "20509876542"])
def test_valid_rucs(ruc):
    assert is_valid_ruc(ruc)


@pytest.mark.parametrize(
    ("ruc", "message"),
    [
        ("20131312954", "dígito verificador"),  # last digit changed
        ("30131312955", "empezar con"),         # prefix that doesn't exist
        ("2013131295", "11 dígitos"),           # too short
        ("2013131295A", "11 dígitos"),          # not numeric
    ],
)
def test_invalid_rucs(ruc, message):
    assert message in ruc_problem(ruc)


# --- Category service ----------------------------------------------------------------------

def test_category_names_are_unique_ignoring_case(category):
    with pytest.raises(BusinessRuleError, match="Ya existe"):
        category_service.create_category(name="  ABARROTES ", description=None)


def test_category_can_keep_its_own_name_when_edited(category):
    category_service.update_category(category, name="Abarrotes", description="Arroz, azúcar, aceite")
    assert category.description == "Arroz, azúcar, aceite"


def test_empty_category_can_be_deleted(db, category):
    category_service.delete_category(category)
    assert _get(db, Category, name="Abarrotes") is None


def test_category_with_products_cannot_be_deleted(db, category, make_product):
    make_product()
    with pytest.raises(BusinessRuleError, match="1 producto"):
        category_service.delete_category(category)
    assert _get(db, Category, name="Abarrotes") is not None


def test_category_list_counts_products_and_searches(db, category, make_product):
    db.session.add(Category(name="Limpieza"))
    db.session.commit()
    make_product(sku="A-1")
    make_product(sku="A-2")

    pagination, counts = category_service.paginate_categories(search="", page=1, per_page=10)
    assert [c.name for c in pagination.items] == ["Abarrotes", "Limpieza"]
    assert counts == {category.id: 2}  # categories without products are simply absent (0)

    pagination, _ = category_service.paginate_categories(search="limp", page=1, per_page=10)
    assert [c.name for c in pagination.items] == ["Limpieza"]


def test_search_treats_wildcards_literally(db, category):
    pagination, _ = category_service.paginate_categories(search="%", page=1, per_page=10)
    assert pagination.items == []


# --- Supplier service ----------------------------------------------------------------------

def test_supplier_is_created_with_normalized_data(db):
    supplier = supplier_service.create_supplier(
        name="  Ferretería El Tornillo ", ruc=" 2013131 2955 ", email="Ventas@Tornillo.PE", phone="", is_active=True
    )
    assert supplier.name == "Ferretería El Tornillo"
    assert supplier.ruc == SUNAT_RUC
    assert supplier.email == "ventas@tornillo.pe"
    assert supplier.phone is None


def test_supplier_service_rejects_invalid_ruc_even_without_the_form(db):
    with pytest.raises(BusinessRuleError, match="dígito verificador"):
        supplier_service.create_supplier(name="Proveedor X", ruc="20131312954", is_active=True)


def test_supplier_ruc_must_be_unique(supplier):
    with pytest.raises(BusinessRuleError, match="ya está registrado para 'Distribuidora Lima SAC'"):
        supplier_service.create_supplier(name="Otro", ruc=supplier.ruc, is_active=True)


def test_suppliers_without_ruc_are_allowed(db):
    supplier_service.create_supplier(name="Mercado mayorista A", ruc="", is_active=True)
    supplier_service.create_supplier(name="Mercado mayorista B", ruc=None, is_active=True)
    assert db.session.execute(db.select(db.func.count(Supplier.id))).scalar() == 2


def test_supplier_with_products_cannot_be_deleted(db, supplier, make_product):
    make_product(supplier=supplier)
    with pytest.raises(BusinessRuleError, match="desactivarlo"):
        supplier_service.delete_supplier(supplier)
    assert supplier.products  # the product still points to its supplier (no silent NULL)


def test_supplier_status_filter(db, supplier):
    supplier_service.create_supplier(name="Antiguo SAC", is_active=False)
    active, _ = supplier_service.paginate_suppliers(status="active")
    inactive, _ = supplier_service.paginate_suppliers(status="inactive")
    everyone, _ = supplier_service.paginate_suppliers(status="all")
    assert [s.name for s in active.items] == ["Distribuidora Lima SAC"]
    assert [s.name for s in inactive.items] == ["Antiguo SAC"]
    assert len(everyone.items) == 2


def test_supplier_search_by_ruc(supplier):
    pagination, _ = supplier_service.paginate_suppliers(search="20600", status="all")
    assert [s.name for s in pagination.items] == ["Distribuidora Lima SAC"]


# --- Routes and permissions ------------------------------------------------------------------

def test_employee_can_list_create_and_edit_catalogs(db, employee, category, client, login):
    login("empleado", "Empleado123")
    assert client.get("/categories/").status_code == 200
    assert client.get("/suppliers/").status_code == 200

    response = client.post("/categories/new", data={"name": "Bebidas", "description": ""})
    assert response.status_code == 302
    response = client.post(f"/categories/{category.id}/edit", data={"name": "Abarrotes finos"})
    assert response.status_code == 302
    assert category.name == "Abarrotes finos"


def test_employee_cannot_delete_catalogs(db, employee, category, supplier, client, login):
    login("empleado", "Empleado123")
    assert client.post(f"/categories/{category.id}/delete").status_code == 403
    assert client.post(f"/suppliers/{supplier.id}/delete").status_code == 403
    assert _get(db, Category, name="Abarrotes") is not None


def test_delete_requires_post(admin, category, client, login):
    login("admin", "Admin123!")
    assert client.get(f"/categories/{category.id}/delete").status_code == 405


def test_admin_deletes_empty_category(db, admin, category, client, login):
    login("admin", "Admin123!")
    response = client.post(f"/categories/{category.id}/delete", follow_redirects=True)
    assert "eliminada" in response.get_data(as_text=True)
    assert _get(db, Category, name="Abarrotes") is None


def test_admin_sees_why_category_cannot_be_deleted(db, admin, category, make_product, client, login):
    make_product()
    login("admin", "Admin123!")
    response = client.post(f"/categories/{category.id}/delete", follow_redirects=True)
    assert "No se puede eliminar" in response.get_data(as_text=True)
    assert _get(db, Category, name="Abarrotes") is not None


def test_supplier_form_shows_ruc_error(admin, client, login):
    login("admin", "Admin123!")
    response = client.post("/suppliers/new", data={"name": "Proveedor X", "ruc": "20131312954", "is_active": "y"})
    assert response.status_code == 200
    assert "dígito verificador" in response.get_data(as_text=True)


def test_admin_creates_supplier_through_the_form(db, admin, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/suppliers/new",
        data={"name": "Distribuidora Norte", "ruc": SUNAT_RUC, "phone": "(01) 634-3300", "is_active": "y"},
    )
    assert response.status_code == 302
    supplier = _get(db, Supplier, ruc=SUNAT_RUC)
    assert supplier.name == "Distribuidora Norte"
    assert supplier.is_active


def test_delete_button_is_hidden_for_employees(employee, category, client, login):
    login("empleado", "Empleado123")
    html = client.get("/categories/").get_data(as_text=True)
    assert "/delete" not in html
