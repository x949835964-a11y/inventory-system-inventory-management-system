"""Reports page and Excel/PDF downloads."""
from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.services import product_service, report_service
from app.services.exceptions import BusinessRuleError
from app.services.exporters import excel, pdf
from app.utils.dates import local_today

bp = Blueprint("reports", __name__, url_prefix="/reports")

MIMETYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
BUILDERS = {
    "inventory": {"xlsx": excel.inventory_xlsx, "pdf": pdf.inventory_pdf},
    "movements": {"xlsx": excel.movements_xlsx, "pdf": pdf.movements_pdf},
}


def _date_arg(name: str) -> date | None:
    try:
        return date.fromisoformat(request.args.get(name, ""))
    except ValueError:
        return None


def _download(kind: str, fmt: str, report, filename: str):
    if fmt not in MIMETYPES:
        abort(404)
    buffer = BUILDERS[kind][fmt](report)
    return send_file(buffer, mimetype=MIMETYPES[fmt], as_attachment=True, download_name=f"{filename}.{fmt}")


@bp.get("/")
@login_required
def index():
    today = local_today(current_app.config["APP_TIMEZONE"])
    return render_template(
        "reports/index.html",
        categories=product_service.category_choices(),
        default_from=today.replace(day=1),
        default_to=today,
        max_days=report_service.MAX_RANGE_DAYS,
    )


@bp.get("/inventory.<fmt>")
@login_required
def inventory(fmt: str):
    try:
        report = report_service.inventory_report(
            category_id=request.args.get("category", type=int),
            stock=request.args.get("stock", ""),
        )
    except BusinessRuleError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("reports.index"))
    return _download("inventory", fmt, report, f"inventario_{report.generated_at:%Y-%m-%d_%H%M}")


@bp.get("/movements.<fmt>")
@login_required
def movements(fmt: str):
    today = local_today(current_app.config["APP_TIMEZONE"])
    date_from = _date_arg("from") or today.replace(day=1)
    date_to = _date_arg("to") or today
    try:
        report = report_service.movements_report(
            date_from=date_from,
            date_to=date_to,
            movement_type=request.args.get("type", ""),
            search=request.args.get("q", "").strip(),
        )
    except BusinessRuleError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("reports.index"))
    return _download("movements", fmt, report, f"movimientos_{date_from:%Y-%m-%d}_a_{date_to:%Y-%m-%d}")
