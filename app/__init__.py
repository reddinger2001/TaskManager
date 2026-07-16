import sys

# Use pysqlite3 instead of system sqlite3 (needed for extension loading)
try:
    import pysqlite3 as _pysqlite3

    sys.modules["sqlite3"] = _pysqlite3
except ImportError:
    pass

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from app.extensions import init_extensions
from app.models import db

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    # Ensure instance directory exists before touching the DB
    import os
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize database and extensions
    init_extensions(app)

    # CSRF protection — only protect POST and DELETE (PATCH is used by Alpine.js API calls)
    app.config["WTF_CSRF_METHODS"] = {"POST", "DELETE"}
    csrf.init_app(app)

    # Register FTS5 hooks (always on — keeps keyword search index in sync)
    from app.services.search import register_fts5_hooks
    register_fts5_hooks(app)

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
