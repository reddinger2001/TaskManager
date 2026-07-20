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
from app.models import Task, User, db

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

    # Require login for all routes except /setup, /login, and /static/
    @app.before_request
    def require_login():
        from flask_login import current_user
        from flask import request
        if not current_user.is_authenticated:
            if request.endpoint in ("auth.login", "auth.setup", "static"):
                return None
            # If no users exist yet, redirect to setup instead of login
            if User.query.first() is None:
                return redirect(url_for("auth.setup"))
            return redirect(url_for("auth.login", next=request.url))

    # Expose scoped_query and user info on g for use in views
    @app.before_request
    def set_scoped_query():
        from flask import g
        from flask_login import current_user
        from app.models import scoped_query
        if current_user.is_authenticated:
            g.scoped_query = lambda model: scoped_query(model, current_user)
            g.current_user = current_user
            g.current_user_id = current_user.id
            g.current_user_is_admin = current_user.is_admin
            g.current_username = current_user.username
        else:
            g.current_user_id = None
            g.current_user_is_admin = False
            g.current_username = ""

    @app.context_processor
    def inject_context():
        """Make user info and app settings available in all templates."""
        from flask import g
        from app.models import AppSettings, Project
        current_user_id = getattr(g, 'current_user_id', None)
        return {
            'current_username': getattr(g, 'current_username', 'anonymous'),
            'current_user_is_admin': getattr(g, 'current_user_is_admin', False),
            'projects': Project.query.order_by(Project.name).all() if current_user_id else [],
            'priorities': AppSettings.get().get_priorities(),
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

    # Migrate: convert any remaining "delegated" tasks to "backlog"
    with app.app_context():
        count = Task.query.filter(Task.status == "delegated").update(
            {Task.status: "backlog"}, synchronize_session=False
        )
        if count:
            db.session.commit()
            app.logger.info(f"Migrated {count} task(s) from 'delegated' to 'backlog'")

    # Migrate: add multi-user support if upgrading from solo mode
    from app.services.migrate import migrate_multi_user
    migrate_multi_user(app)

    # Seed tutorial data on first run (fresh database only)
    from app.services.seed import seed_if_empty
    seed_if_empty(app)

    return app
