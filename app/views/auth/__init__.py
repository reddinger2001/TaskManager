from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import login_user, logout_user

from app.models import AppSettings, User, db

auth_bp = Blueprint("auth", __name__)


def _has_users():
    """Check if any users exist in the database."""
    return User.query.first() is not None


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Initial setup — create the first admin account and configure priorities."""
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    if _has_users():
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        priorities_raw = request.form.get("priorities", "P0, P1, P2").strip()

        errors = []
        if not username or len(username) < 2:
            errors.append("Username must be at least 2 characters")
        if User.query.filter_by(username=username).first():
            errors.append("Username already taken")
        if not password or len(password) < 4:
            errors.append("Password must be at least 4 characters")
        if password != confirm:
            errors.append("Passwords do not match")

        # Parse priorities
        priorities = [p.strip() for p in priorities_raw.split(",") if p.strip()]
        if not priorities:
            errors.append("You must define at least one priority level")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/setup.html", priorities=priorities_raw)

        # Create admin user
        admin = User(username=username, is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.flush()

        # Save app settings
        settings = AppSettings.get()
        settings.set_priorities(priorities)
        db.session.commit()

        login_user(admin, remember=True)
        flash("Setup complete! Welcome to TaskManager.", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/setup.html", priorities="P0, P1, P2")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    from flask_login import current_user
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.index"))

        if not user:
            flash("User \"" + username + "\" not found", "error")
        else:
            flash("Incorrect password for \"" + username + "\"", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    from flask_login import current_user
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("main.index"))
