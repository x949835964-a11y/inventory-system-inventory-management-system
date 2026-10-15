"""Inventory movements: list, register entries/exits and the per-product kardex."""
from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.movement_forms import EntryForm, ExitForm
from app.models import MovementReason, MovementType, Product
from app.services import kardex_service, movement_service, stock_service
from app.services.exceptions import BusinessRuleError
from app.services.movement_service import MovementFilters
from app.utils.dates import local_today, movement_datetime
from app.utils.formatters import quantity as fmt_qty

bp = Blueprint("movements", __name__, url_prefix="/movements")

FORMS = {"in": EntryForm, "out": ExitForm}


def _tz() -> str:
    return current_app.config["APP_TIMEZONE"]


def _date_arg(name: str) -> date | None:
    """Parse ?from=YYYY-MM-DD safely; an invalid date is simply ignored."""
    try:
        return date.fromisoformat(request.args.get(name, ""))
    except ValueError:
        return None


@bp.get("/")
@login_required
def index():
    filters = MovementFilters(
        search=request.args.get("q", "").strip(),
        movement_type=request.args.get("type", ""),
        reason=request.args.get("reason", ""),
        date_from=_date_arg("from"),
        date_to=_date_arg("to"),
    )
    page = request.args.get("page", 1, type=int)
    pagination = movement_service.paginate_movements(filters, _tz(), page, current_app.config["ITEMS_PER_PAGE"])
    return render_template(
        "movements/list.html", pagination=pagination, filters=filters, reasons=list(MovementReason)
    )


@bp.route("/new/<movement_type>", methods=["GET", "POST"])
@login_required
def create(movement_type: str):
    if movement_type not in FORMS:
        abort(404)
    direction = MovementType(movement_type)
    form = FORMS[movement_type]()
    form.product_id.choices = [(0, "— Selecciona un producto —")] + movement_service.product_choices()
    form.reason.choices = movement_service.reason_choices(direction, current_user)
    if request.method == "GET":
        form.product_id.data = request.args.get("product_id", 0, type=int)

    if form.validate_on_submit():
        is_entry = direction == MovementType.IN
        try:
            movement = stock_service.register_movement(
                product_id=form.product_id.data,
                movement_type=direction,
                reason=MovementReason(form.reason.data),
                quantity=form.quantity.data,
                user=current_user,
                unit_cost=form.unit_cost.data if is_entry else None,
                update_cost=form.update_cost.data if is_entry else False,
                movement_date=movement_datetime(form.movement_date.data, _tz()),
                notes=form.notes.data,
            )
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            product = movement.product
            flash(
                f"{direction.label} registrada: {fmt_qty(movement.quantity)} {product.unit} de '{product.name}'. "
                f"Stock actual: {fmt_qty(product.stock)} {product.unit}.",
                "success",
            )
            if product.is_low_stock:
                flash(f"'{product.name}' quedó en o por debajo del stock mínimo. Conviene reponer.", "warning")
            return redirect(url_for("products.detail", product_id=product.id))

    return render_template("movements/form.html", form=form, direction=direction)


@bp.get("/kardex/<int:product_id>")
@login_required
def kardex(product_id: int):
    product = db.get_or_404(Product, product_id)
    if not product.is_active and not current_user.is_admin:
        abort(404)
    today = local_today(_tz())
    date_from = _date_arg("from") or today.replace(day=1)  # default: current month
    date_to = _date_arg("to") or today
    report = kardex_service.build_kardex(product, date_from, date_to, _tz())
    return render_template("movements/kardex.html", kardex=report, product=product)
