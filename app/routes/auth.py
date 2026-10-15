"""Login, logout and own-password change."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms.auth_forms import ChangePasswordForm, LoginForm
from app.services.auth_service import authenticate
from app.services.exceptions import AuthenticationError, BusinessRuleError
from app.services.user_service import change_own_password
from app.utils.security import is_safe_redirect

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = authenticate(form.username.data, form.password.data)
        except AuthenticationError as exc:
            flash(str(exc), "danger")
        else:
            login_user(user, remember=form.remember.data)
            flash(f"Bienvenido, {user.full_name}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url if is_safe_redirect(next_url) else url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.post("/logout")  # POST + CSRF token: a malicious <img src=".../logout"> can't log you out
@login_required
def logout():
    logout_user()
    flash("Cerraste sesión correctamente.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        try:
            change_own_password(
                current_user,
                current_password=form.current_password.data,
                new_password=form.new_password.data,
            )
        except BusinessRuleError as exc:
            flash(str(exc), "danger")
        else:
            flash("Tu contraseña fue actualizada.", "success")
            return redirect(url_for("main.index"))
    return render_template("auth/change_password.html", form=form)
