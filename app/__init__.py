import sys

# Use pysqlite3 instead of system sqlite3 (needed for extension loading)
try:
    import pysqlite3 as _pysqlite3

    sys.modules["sqlite3"] = _pysqlite3
except ImportError:
    pass

from flask import Flask

from app.extensions import init_extensions
from app.models import db


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    # Initialize database and extensions
    init_extensions(app)

    # Register embedding hooks (after_commit → sync embed + FTS5)
    from app.services.embedding import register_embedding_hooks, register_fts5_hooks
    register_embedding_hooks(app)
    register_fts5_hooks(app)

    from app.views.main import main_bp
    app.register_blueprint(main_bp)

    from app.views.projects import projects_bp
    app.register_blueprint(projects_bp)

    from app.views.logs import logs_bp
    app.register_blueprint(logs_bp)

    from app.views.tasks import tasks_bp
    app.register_blueprint(tasks_bp)

    return app
