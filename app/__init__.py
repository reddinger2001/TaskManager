import sys

# Use pysqlite3 instead of system sqlite3 (needed for extension loading)
try:
    import pysqlite3 as _pysqlite3

    sys.modules["sqlite3"] = _pysqlite3
except ImportError:
    pass

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from app.extensions import init_extensions
from app.models import User, db

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    # Ensure instance directory exists before touching the DB
    import os
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize database and extensions
    init_extensions(app)

    # Flask-Login
    login_manager.init_app(app)

    # Require login for all routes except /login and /static/
    @app.before_request
    def require_login():
        from flask_login import current_user
        from flask import request
        if not current_user.is_authenticated and request.endpoint not in ("auth.login", "static"):
            return redirect(url_for("auth.login", next=request.url))

    # Expose scoped_query and user info on g for use in views
    @app.before_request
    def set_scoped_query():
        from flask import g
        from flask_login import current_user
        from app.models import scoped_query
        if current_user.is_authenticated:
            g.scoped_query = lambda model: scoped_query(model, current_user)
            g.current_user_id = current_user.id
            g.current_user_is_admin = current_user.is_admin
            g.current_username = current_user.username
        else:
            g.current_user_id = None
            g.current_user_is_admin = False
            g.current_username = ""

    @app.context_processor
    def inject_user_context():
        """Make user info available in all templates via template context."""
        from flask import g
        return {
            'current_username': getattr(g, 'current_username', 'anonymous'),
            'current_user_is_admin': getattr(g, 'current_user_is_admin', False),
        }

    # CSRF protection — only protect POST and DELETE (PATCH is used by Alpine.js API calls)
    app.config["WTF_CSRF_METHODS"] = {"POST", "DELETE"}
    csrf.init_app(app)

    # Register FTS5 hooks (always on — keeps keyword search index in sync)
    from app.services.search import register_fts5_hooks
    register_fts5_hooks(app)

    from app.views.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.views.main import main_bp
    app.register_blueprint(main_bp)

    from app.views.projects import projects_bp
    app.register_blueprint(projects_bp)

    from app.views.logs import logs_bp
    app.register_blueprint(logs_bp)

    from app.views.tasks import tasks_bp
    app.register_blueprint(tasks_bp)

    # In-app help system
    from app.views.help import help_bp
    app.register_blueprint(help_bp)

    # Seed tutorial data on first run (fresh database only)
    from app.services.seed import seed_if_empty
    seed_if_empty(app)

    return app
