import os

try:
    import pysqlite3 as sqlite3  # noqa: F401 — needed for extension loading
except ImportError:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'taskmanager.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
