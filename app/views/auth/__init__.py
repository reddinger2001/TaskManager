from flask import Blueprint, redirect, render_template, request, url_for, flash
from flask_login import login_user, logout_user

from app.models import User, db

auth_bp = Blueprint("auth", __name__)


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

        flash("Invalid username or password", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    from flask_login import current_user
    if current_user.is_authenticated:
        logout_user()
    return redirect(url_for("main.index"))
