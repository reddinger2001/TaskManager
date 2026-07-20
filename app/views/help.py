"""In-app help documentation — served as static HTML pages."""

from flask import Blueprint, render_template

help_bp = Blueprint("help", __name__, url_prefix="/help")

HELP_PAGES = {
    "getting-started": "Getting Started",
    "dashboard": "Dashboard",
    "tasks": "Tasks & Statuses",
    "projects": "Projects",
    "search": "Search",
    "dependencies": "Dependencies",
    "multi-user": "Multi-User Setup",
    "user-management": "User Management",
    "backup-restore": "Backup & Restore",
}

@help_bp.route("/")
def help_index():
    """Help index page listing all topics."""
    return render_template("help/index.html", pages=HELP_PAGES)


@help_bp.route("/<page>")
def help_page(page):
    """Individual help topic page."""
    if page not in HELP_PAGES:
        from flask import abort
        abort(404)
    return render_template(f"help/{page}.html", pages=HELP_PAGES, active_page=page)
