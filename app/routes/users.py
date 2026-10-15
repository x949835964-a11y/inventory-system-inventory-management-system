"""User management. Every view is restricted to administrators."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.forms.user_forms import ResetPasswordForm, UserCreateForm, UserEditForm
from app.models import User, UserRole
from app.services import user_service
from app.services.exceptions import BusinessRuleError
from app.utils.decorators import admin_required

bp = Blueprint("users", __name__, url_prefix="/users")


@bp.get("/")
@admin_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = user_service.paginate_users(page, current_app.config["ITEMS_PER_PAGE"])
    return render_template("users/list.html", pagination=pagination)


@bp.route("/new", methods=["GET", "POST"])
@admin_required
def create():
    form = UserCreateForm()
    if form.validate_on_submit():
        try:
            user = user_service.create_user(
                username=form.username.data,
                full_name=form.full_name.data,
                password=form.password.data,
                role=UserRole(form.role.data),
            )
        except BusinessRuleError as exc:
            form.username.errors.append(str(exc))
        else:
            flash(f"Usuario '{user.username}' creado.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form, user=None)


@bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit(user_id: int):
    user = db.get_or_404(User, user_id)
    form = UserEditForm(obj=user)
    if request.method == "GET":
        form.role.data = user.role.value  # the select expects the enum's value, not the enum

    if form.validate_on_submit():
        try:
            user_service.update_user(
                user,
                full_name=form.full_name.data,
                role=UserRole(form.role.data),
                is_active=form.is_active.data,
                acting_user=current_user,
            )
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Usuario '{user.username}' actualizado.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form, user=user)


@bp.route("/<int:user_id>/password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id: int):
    user = db.get_or_404(User, user_id)
    form = ResetPasswordForm()
    if form.validate_on_submit():
        try:
            user_service.reset_password(user, form.new_password.data)
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash(f"Contraseña de '{user.username}' restablecida.", "success")
            return redirect(url_for("users.index"))
    return render_template("users/reset_password.html", form=form, user=user)
