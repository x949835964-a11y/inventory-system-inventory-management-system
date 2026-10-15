"""Categories: every user can list, create and edit; only administrators delete."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.forms.catalog_forms import CategoryForm
from app.models import Category
from app.services import category_service
from app.services.exceptions import BusinessRuleError
from app.utils.decorators import admin_required

bp = Blueprint("categories", __name__, url_prefix="/categories")


@bp.get("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    pagination, counts = category_service.paginate_categories(
        search=search, page=page, per_page=current_app.config["ITEMS_PER_PAGE"]
    )
    return render_template("categories/list.html", pagination=pagination, counts=counts, search=search)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            category = category_service.create_category(name=form.name.data, description=form.description.data)
        except BusinessRuleError as exc:
            form.name.errors.append(str(exc))
        else:
            flash(f"Categoría '{category.name}' creada.", "success")
            return redirect(url_for("categories.index"))
    return render_template("categories/form.html", form=form, category=None)


@bp.route("/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
def edit(category_id: int):
    category = db.get_or_404(Category, category_id)
    form = CategoryForm(obj=category)
    if form.validate_on_submit():
        try:
            category_service.update_category(category, name=form.name.data, description=form.description.data)
        except BusinessRuleError as exc:
            form.name.errors.append(str(exc))
        else:
            flash(f"Categoría '{category.name}' actualizada.", "success")
            return redirect(url_for("categories.index"))
    return render_template("categories/form.html", form=form, category=category)


@bp.post("/<int:category_id>/delete")
@admin_required
def delete(category_id: int):
    category = db.get_or_404(Category, category_id)
    name = category.name
    try:
        category_service.delete_category(category)
    except BusinessRuleError as exc:
        flash(str(exc), "danger")
    else:
        flash(f"Categoría '{name}' eliminada.", "success")
    return redirect(url_for("categories.index"))
