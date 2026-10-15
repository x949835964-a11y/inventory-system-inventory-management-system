"""Suppliers: every user can list, create and edit; only administrators delete."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.forms.catalog_forms import SupplierForm
from app.models import Supplier
from app.services import supplier_service
from app.services.exceptions import BusinessRuleError
from app.utils.decorators import admin_required

bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")

FORM_FIELDS = ("name", "ruc", "phone", "email", "address", "contact_name", "is_active")


def _form_data(form: SupplierForm) -> dict:
    return {field: getattr(form, field).data for field in FORM_FIELDS}


@bp.get("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "active")
    page = request.args.get("page", 1, type=int)
    pagination, counts = supplier_service.paginate_suppliers(
        search=search, status=status, page=page, per_page=current_app.config["ITEMS_PER_PAGE"]
    )
    return render_template(
        "suppliers/list.html", pagination=pagination, counts=counts, search=search, status=status
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = SupplierForm()
    if form.validate_on_submit():
        try:
            supplier = supplier_service.create_supplier(**_form_data(form))
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Proveedor '{supplier.name}' creado.", "success")
            return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", form=form, supplier=None)


@bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
def edit(supplier_id: int):
    supplier = db.get_or_404(Supplier, supplier_id)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        try:
            supplier_service.update_supplier(supplier, **_form_data(form))
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Proveedor '{supplier.name}' actualizado.", "success")
            return redirect(url_for("suppliers.index"))
    return render_template("suppliers/form.html", form=form, supplier=supplier)


@bp.post("/<int:supplier_id>/delete")
@admin_required
def delete(supplier_id: int):
    supplier = db.get_or_404(Supplier, supplier_id)
    name = supplier.name
    try:
        supplier_service.delete_supplier(supplier)
    except BusinessRuleError as exc:
        flash(str(exc), "danger")
    else:
        flash(f"Proveedor '{name}' eliminado.", "success")
    return redirect(url_for("suppliers.index", status="all"))
