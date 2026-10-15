"""Custom error pages for the whole application."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_wtf.csrf import CSRFError

from app.extensions import db
from app.utils.security import is_safe_redirect

bp = Blueprint("errors", __name__)


@bp.app_errorhandler(403)
def forbidden(_error):
    return render_template("errors/403.html"), 403


@bp.app_errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


@bp.app_errorhandler(500)
def internal_error(_error):
    # A failed transaction leaves the session unusable; reset it so the next request works.
    db.session.rollback()
    return render_template("errors/500.html"), 500


@bp.app_errorhandler(CSRFError)
def csrf_error(_error):
    """Usually a form left open too long: explain it instead of showing a bare 400."""
    flash("El formulario expiró o no es válido. Inténtalo de nuevo.", "warning")
    referrer = request.referrer or ""
    # Keep only the path of our own referrer, never redirect to an external URL.
    path = referrer.removeprefix(request.host_url.rstrip("/"))
    return redirect(path if is_safe_redirect(path) else url_for("main.index"))
