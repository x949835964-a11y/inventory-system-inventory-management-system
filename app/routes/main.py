"""Main blueprint: dashboard and health check."""
from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required
from sqlalchemy import text

from app.extensions import db
from app.services import dashboard_service

bp = Blueprint("main", __name__)


@bp.get("/")
@login_required
def index():
    tz = current_app.config["APP_TIMEZONE"]
    return render_template(
        "dashboard/index.html",
        summary=dashboard_service.get_summary(tz),
        restock=dashboard_service.restock_list(),
        recent=dashboard_service.recent_movements(),
        # Embedded as JSON in the page: one request, no extra API endpoint to secure.
        chart_data=dashboard_service.daily_flow(tz),
    )


@bp.get("/health")
def health():
    """Liveness check used after deploying: confirms the app can reach the database."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="ok")
    except Exception:  # noqa: BLE001 - any DB failure means "unhealthy"
        return jsonify(status="error", database="unreachable"), 503
