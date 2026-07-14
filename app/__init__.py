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

    # Initialize database and extensions
    init_extensions(app)

    # CSRF protection — exclude PATCH endpoints (JSON API calls from Alpine.js)
    app.config["WTF_CSRF_EXEMPT_METHODS"] = ["PATCH", "GET", "OPTIONS", "HEAD"]
    csrf.init_app(app)

    # Register FTS5 hooks (always on — keeps keyword search index in sync)
    from app.services.embedding import register_fts5_hooks
    register_fts5_hooks(app)

    # Register embedding hooks only if enabled (disabled by default — model crashes Python)
    if app.config.get("EMBEDDING_ENABLED", False):
        from app.services.embedding import register_embedding_hooks
        register_embedding_hooks(app)

    from app.views.main import main_bp
    app.register_blueprint(main_bp)

    from app.views.projects import projects_bp
    app.register_blueprint(projects_bp)

    from app.views.logs import logs_bp
    app.register_blueprint(logs_bp)

    from app.views.tasks import tasks_bp
    app.register_blueprint(tasks_bp)

    return app
