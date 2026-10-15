"""Authentication: login, logout, sessions and redirect safety."""
import pytest

from app.services.auth_service import authenticate
from app.services.exceptions import AuthenticationError
from app.utils.security import is_safe_redirect, password_problem


def _logged_user_id(client):
    with client.session_transaction() as session:
        return session.get("_user_id")


# --- Service -----------------------------------------------------------------------

def test_authenticate_accepts_valid_credentials_and_records_login(admin):
    user = authenticate("ADMIN ", "Admin123!")  # username is case/space insensitive
    assert user.id == admin.id
    assert user.last_login_at is not None


@pytest.mark.parametrize(("username", "password"), [("admin", "wrong"), ("nobody", "Admin123!")])
def test_authenticate_gives_the_same_message_for_bad_user_or_password(admin, username, password):
    # Same message in both cases: an attacker can't learn which usernames exist.
    with pytest.raises(AuthenticationError, match="Usuario o contraseña incorrectos"):
        authenticate(username, password)


def test_authenticate_rejects_inactive_user(db, employee):
    employee.is_active = False
    db.session.commit()
    with pytest.raises(AuthenticationError, match="desactivada"):
        authenticate("empleado", "Empleado123")


# --- Routes ------------------------------------------------------------------------

def test_login_page_renders(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "Iniciar sesión" in response.get_data(as_text=True)


def test_successful_login_redirects_to_dashboard(admin, client, login):
    response = login("admin", "Admin123!")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert _logged_user_id(client) == str(admin.id)


def test_failed_login_shows_error_and_does_not_log_in(admin, client, login):
    response = login("admin", "wrong-password", follow_redirects=True)
    assert "Usuario o contraseña incorrectos" in response.get_data(as_text=True)
    assert _logged_user_id(client) is None


def test_protected_page_redirects_anonymous_user_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/auth/login?next=")


def test_login_follows_safe_next_url(admin, login):
    response = login("admin", "Admin123!", next_url="/users/")
    assert response.headers["Location"] == "/users/"


def test_login_ignores_external_next_url(admin, login):
    response = login("admin", "Admin123!", next_url="https://evil.example.com")
    assert response.headers["Location"] == "/"


def test_logout_requires_post(admin, client, login):
    login("admin", "Admin123!")
    assert client.get("/auth/logout").status_code == 405
    response = client.post("/auth/logout")
    assert response.status_code == 302
    assert _logged_user_id(client) is None


def test_deactivated_user_loses_open_session(db, employee, client, login):
    login("empleado", "Empleado123")
    assert client.get("/").status_code == 200

    employee.is_active = False
    db.session.commit()

    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_without_csrf_token_is_rejected(app, admin, client, login):
    app.config["WTF_CSRF_ENABLED"] = True
    response = login("admin", "Admin123!")
    assert response.status_code == 302  # back to a page with an explanatory flash message
    assert _logged_user_id(client) is None


def test_change_own_password(admin, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/auth/password",
        data={"current_password": "Admin123!", "new_password": "NuevaClave1", "confirm_password": "NuevaClave1"},
    )
    assert response.status_code == 302
    assert admin.check_password("NuevaClave1")


def test_change_password_rejects_wrong_current_password(admin, client, login):
    login("admin", "Admin123!")
    response = client.post(
        "/auth/password",
        data={"current_password": "otra", "new_password": "NuevaClave1", "confirm_password": "NuevaClave1"},
    )
    assert response.status_code == 200
    assert "La contraseña actual no es correcta" in response.get_data(as_text=True)
    assert admin.check_password("Admin123!")


# --- Security helpers ----------------------------------------------------------------

@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("/users/", True),
        ("/products/?page=2", True),
        ("https://evil.example.com", False),
        ("//evil.example.com", False),
        ("/\\evil.example.com", False),
        ("javascript:alert(1)", False),
        ("", False),
        (None, False),
    ],
)
def test_is_safe_redirect(target, expected):
    assert is_safe_redirect(target) is expected


@pytest.mark.parametrize(
    ("password", "is_valid"),
    [("Admin123", True), ("corto1", False), ("solotexto", False), ("12345678", False)],
)
def test_password_policy(password, is_valid):
    assert (password_problem(password) is None) is is_valid
