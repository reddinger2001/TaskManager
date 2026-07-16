"""Database extensions: FTS5 setup."""

from app.models import db


def init_extensions(app):
    """Initialize FTS5 on the database.

    Called once after create_all(). Sets up:
    - FTS5 virtual table for keyword search
    """
    db.init_app(app)

    with app.app_context():
        # Create all tables first
        db.create_all()

        # Create FTS5 virtual table for keyword search
        try:
            raw_conn = db.engine.raw_connection()
            raw_conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5("
                "task_id UNINDEXED, title, description, tags_text"
                ")"
            )
            raw_conn.commit()
            raw_conn.close()
        except Exception as e:
            app.logger.warning(f"Could not create search_index table: {e}")
