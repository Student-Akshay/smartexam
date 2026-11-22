"""
auth/routes.py
--------------
Handles student & admin registration, login, and logout.
All views are accessible without authentication.
"""

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, session
)
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Student self-registration page."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        full_name  = request.form.get("full_name",  "").strip()
        email      = request.form.get("email",      "").strip().lower()
        password   = request.form.get("password",   "")
        confirm_pw = request.form.get("confirm_password", "")

        # ---- Validation ----
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_pw:
            errors.append("Passwords do not match.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "auth/register.html",
                full_name=full_name, email=email
            )

        # ---- Create user ----
        user = User(full_name=full_name, email=email, role="student")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Shared login page for students and admins."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        email    = request.form.get("email",    "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            return redirect(url_for("student.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


# ------------------------------------------------------------------
# Logout
# ------------------------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    """Log out the current user."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
