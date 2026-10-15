"""Role-based access and user management rules."""
import pytest

from app.models import User, UserRole
from app.services import user_service
from app.services.exceptions import BusinessRuleError


# --- Access control --------------------------------------------------------------------

def test_employee_cannot_access_user_management(employee, client, login):
    login("empleado", "Empleado123")
    for url in ("/users/", "/users/new", "/users/1/edit", "/users/1/password"):
        assert client.get(url).status_code == 403, url


def test_admin_can_access_user_management(admin, client, login):
    login("admin", "Admin123!")
    assert client.get("/users/").status_code == 200
    assert client.get("/users/new").status_code == 200


def test_anonymous_user_is_sent_to_login_not_403(client):
    response = client.get("/users/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_menu_shows_users_link_only_to_admin(admin, employee, app, login):
    admin_client, employee_client = app.test_client(), app.test_client()
    admin_client.post("/auth/login", data={"username": "admin", "password": "Admin123!"})
    employee_client.post("/auth/login", data={"username": "empleado", "password": "Empleado123"})

    assert 'href="/users/"' in admin_client.get("/").get_data(as_text=True)
    assert 'href="/users/"' not in employee_client.get("/").get_data(as_text=True)


def test_unknown_user_returns_404(admin, client, login):
    login("admin", "Admin123!")
    assert client.get("/users/9999/edit").status_code == 404


# --- Create / edit through the routes ---------------------------------------------------------

def test_admin_creates_user(db, admin, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/users/new",
        data={
            "username": "MRojas",
            "full_name": "María Rojas",
            "role": "employee",
            "password": "Clave1234",
            "confirm_password": "Clave1234",
        },
    )
    assert response.status_code == 302

    user = db.session.execute(db.select(User).filter_by(username="mrojas")).scalar_one()
    assert user.role == UserRole.EMPLOYEE
    assert user.check_password("Clave1234")


def test_create_user_rejects_duplicate_username(admin, employee, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/users/new",
        data={
            "username": "EMPLEADO",
            "full_name": "Otro",
            "role": "employee",
            "password": "Clave1234",
            "confirm_password": "Clave1234",
        },
    )
    assert response.status_code == 200
    assert "ya existe" in response.get_data(as_text=True)


def test_create_user_rejects_weak_password(admin, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/users/new",
        data={"username": "nuevo", "full_name": "Nuevo", "role": "employee",
              "password": "abc", "confirm_password": "abc"},
    )
    assert response.status_code == 200
    assert "al menos 8 caracteres" in response.get_data(as_text=True)


def test_admin_deactivates_employee(admin, employee, client, login):
    login("admin", "Admin123!")
    response = client.post(
        f"/users/{employee.id}/edit",
        data={"full_name": "Empleado Demo", "role": "employee"},  # unchecked box -> inactive
    )
    assert response.status_code == 302
    assert employee.is_active is False


def test_admin_resets_employee_password(admin, employee, client, login):
    login("admin", "Admin123!")
    response = client.post(
        f"/users/{employee.id}/password",
        data={"new_password": "Reinicio123", "confirm_password": "Reinicio123"},
    )
    assert response.status_code == 302
    assert employee.check_password("Reinicio123")


# --- Service rules ------------------------------------------------------------------------

def test_admin_cannot_demote_self(admin):
    with pytest.raises(BusinessRuleError):
        user_service.update_user(admin, full_name="Admin", role=UserRole.EMPLOYEE, is_active=True, acting_user=admin)
    assert admin.role == UserRole.ADMIN


def test_admin_cannot_deactivate_self(admin):
    with pytest.raises(BusinessRuleError):
        user_service.update_user(admin, full_name="Admin", role=UserRole.ADMIN, is_active=False, acting_user=admin)
    assert admin.is_active


def test_admin_can_promote_employee(admin, employee):
    user_service.update_user(
        employee, full_name="Empleado Demo", role=UserRole.ADMIN, is_active=True, acting_user=admin
    )
    assert employee.is_admin


def test_change_own_password_requires_a_different_password(admin):
    with pytest.raises(BusinessRuleError, match="distinta"):
        user_service.change_own_password(admin, current_password="Admin123!", new_password="Admin123!")
