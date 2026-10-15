"""Products: every user lists, creates and edits; only administrators deactivate or reactivate."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.product_forms import ProductCreateForm, ProductForm
from app.models import Product
from app.services import product_service
from app.services.exceptions import BusinessRuleError
from app.services.product_service import ProductFilters
from app.utils.decorators import admin_required

bp = Blueprint("products", __name__, url_prefix="/products")

FORM_FIELDS = product_service.EDITABLE_FIELDS


def _filters_from_request() -> ProductFilters:
    status = request.args.get("status", "active")
    if not current_user.is_admin:
        status = "active"  # employees never see deactivated products
    return ProductFilters(
        search=request.args.get("q", "").strip(),
        category_id=request.args.get("category", type=int),
        stock=request.args.get("stock", ""),
        status=status,
        sort=request.args.get("sort", "name"),
    )


def _load_choices(form: ProductForm, product: Product | None = None) -> None:
    form.category_id.choices = [(0, "— Selecciona una categoría —")] + product_service.category_choices()
    current_supplier = product.supplier_id if product else None
    form.supplier_id.choices = [(0, "— Sin proveedor —")] + product_service.supplier_choices(current_supplier)


def _form_data(form: ProductForm) -> dict:
    return {field: getattr(form, field).data for field in FORM_FIELDS}


def _warn_if_selling_below_cost(product: Product) -> None:
    # Allowed (liquidations happen), but it's almost always a typo worth pointing out.
    if product.sale_price < product.purchase_price:
        flash("Atención: el precio de venta es menor que el precio de compra.", "warning")


@bp.get("/")
@login_required
def index():
    filters = _filters_from_request()
    page = request.args.get("page", 1, type=int)
    pagination = product_service.paginate_products(filters, page, current_app.config["ITEMS_PER_PAGE"])
    return render_template(
        "products/list.html",
        pagination=pagination,
        filters=filters,
        categories=product_service.category_choices(),
        low_stock_total=product_service.low_stock_count(),
    )


@bp.get("/<int:product_id>")
@login_required
def detail(product_id: int):
    product = db.get_or_404(Product, product_id)
    if not product.is_active and not current_user.is_admin:
        abort(404)  # deactivated products are invisible to employees
    return render_template(
        "products/detail.html", product=product, movements=product_service.recent_movements(product)
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = ProductCreateForm()
    _load_choices(form)
    if form.validate_on_submit():
        try:
            product = product_service.create_product(
                _form_data(form), initial_stock=form.initial_stock.data, user=current_user
            )
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Producto '{product.name}' registrado con SKU {product.sku}.", "success")
            _warn_if_selling_below_cost(product)
            return redirect(url_for("products.detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=None)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id: int):
    product = db.get_or_404(Product, product_id)
    if not product.is_active:
        flash("Reactiva el producto antes de editarlo.", "warning")
        return redirect(url_for("products.detail", product_id=product.id))

    form = ProductForm(obj=product)
    _load_choices(form, product)
    if request.method == "GET":
        form.supplier_id.data = product.supplier_id or 0

    if form.validate_on_submit():
        try:
            product_service.update_product(product, _form_data(form))
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Producto '{product.name}' actualizado.", "success")
            _warn_if_selling_below_cost(product)
            return redirect(url_for("products.detail", product_id=product.id))
    return render_template("products/form.html", form=form, product=product)


@bp.post("/<int:product_id>/deactivate")
@admin_required
def deactivate(product_id: int):
    product = db.get_or_404(Product, product_id)
    try:
        product_service.deactivate_product(product)
    except BusinessRuleError as exc:
        flash(str(exc), "warning")
    else:
        flash(f"Producto '{product.name}' desactivado. Su historial se conserva.", "success")
    return redirect(url_for("products.index"))


@bp.post("/<int:product_id>/activate")
@admin_required
def activate(product_id: int):
    product = db.get_or_404(Product, product_id)
    try:
        product_service.reactivate_product(product)
    except BusinessRuleError as exc:
        flash(str(exc), "warning")
    else:
        flash(f"Producto '{product.name}' reactivado.", "success")
    return redirect(url_for("products.detail", product_id=product.id))
