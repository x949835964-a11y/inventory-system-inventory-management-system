"""Application factory."""
import os
from datetime import datetime

from flask import Flask

from app.config import config_by_name
from app.extensions import csrf, db, login_manager, migrate

# Navigation menu: (endpoint, label, Bootstrap icon, admin only).
# Only entries whose endpoint exists are shown, so the menu grows with each module.
NAV_ITEMS = [
    ("main.index", "Dashboard", "speedometer2", False),
    ("products.index", "Productos", "box-seam", False),
    ("movements.index", "Movimientos", "arrow-left-right", False),
    ("categories.index", "Categorías", "tags", False),
    ("suppliers.index", "Proveedores", "truck", False),
    ("reports.index", "Reportes", "file-earmark-bar-graph", False),
    ("users.index", "Usuarios", "people", True),
]


def create_app(config_name: str | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    config_name = config_name or os.environ.get("APP_ENV", "development")
    if config_name not in config_by_name:
        raise ValueError(f"Unknown APP_ENV '{config_name}'. Use: {', '.join(config_by_name)}")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    _validate_config(app)
    if app.config.get("BEHIND_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    _register_extensions(app)
    _register_blueprints(app)
    _register_template_helpers(app)
    _register_shell_context(app)

    from app.cli import register_cli

    register_cli(app)
    return app


def _validate_config(app: Flask) -> None:
    """Fail fast with a clear message instead of a cryptic error later."""
    missing = [key for key in ("SECRET_KEY", "SQLALCHEMY_DATABASE_URI") if not app.config.get(key)]
    if missing:
        names = ", ".join("DATABASE_URL" if k == "SQLALCHEMY_DATABASE_URI" else k for k in missing)
        raise RuntimeError(f"Missing environment variables: {names}. Copy .env.example to .env and fill them in.")


def _register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import models so SQLAlchemy and Alembic know every table.
    from app import models  # noqa: F401


def _register_blueprints(app: Flask) -> None:
    from app.routes.auth import bp as auth_bp
    from app.routes.categories import bp as categories_bp
    from app.routes.errors import bp as errors_bp
    from app.routes.main import bp as main_bp
    from app.routes.movements import bp as movements_bp
    from app.routes.products import bp as products_bp
    from app.routes.reports import bp as reports_bp
    from app.routes.suppliers import bp as suppliers_bp
    from app.routes.users import bp as users_bp

    for blueprint in (main_bp, auth_bp, users_bp, categories_bp, suppliers_bp, products_bp, movements_bp, reports_bp, errors_bp):
        app.register_blueprint(blueprint)


def _register_template_helpers(app: Flask) -> None:
    from app.utils.formatters import local_datetime, money, quantity

    app.add_template_filter(local_datetime, "local_dt")
    app.add_template_filter(money, "money")
    app.add_template_filter(quantity, "qty")

    @app.context_processor
    def inject_globals():
        nav_items = [item for item in NAV_ITEMS if item[0] in app.view_functions]
        context = {"nav_items": nav_items, "current_year": datetime.now().year}
        if app.config.get("DEMO_MODE"):
            from app.demo import DEMO_ACCOUNTS

            context["demo_accounts"] = DEMO_ACCOUNTS
        return context


def _register_shell_context(app: Flask) -> None:
    """Expose db and models in `flask shell` for quick debugging."""
    from app import models

    @app.shell_context_processor
    def shell_context():
        return {
            "db": db,
            "User": models.User,
            "Category": models.Category,
            "Supplier": models.Supplier,
            "Product": models.Product,
            "StockMovement": models.StockMovement,
        }
