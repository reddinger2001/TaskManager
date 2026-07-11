"""Database extensions: sqlite-vec and FTS5 setup."""

import pysqlite3 as sqlite3
import sqlite_vec

from flask import g

from app.models import db


def init_extensions(app):
    """Initialize sqlite-vec and FTS5 on the database.

    Called once after create_all(). Sets up:
    - sqlite-vec extension (loaded via pysqlite3 for extension support)
    - vec0 virtual table for task embeddings (384-dim vectors)
    - FTS5 virtual table for keyword search
    """
    db.init_app(app)

    with app.app_context():
        # Create all tables first
        db.create_all()

        # Get raw connection and load sqlite-vec
        raw_conn = db.engine.raw_connection()
        try:
            raw_conn.enable_load_extension(True)
            sqlite_vec.load(raw_conn)
        except AttributeError:
            # System SQLite may not support extensions — skip gracefully
            app.logger.warning("sqlite-vec extension could not be loaded (SQLite compiled without load_extension)")

        # Create vec0 table for embeddings
        try:
            raw_conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS task_embeddings USING vec0("
                "task_id INTEGER PRIMARY KEY, embedding float[384]"
                ")"
            )
            raw_conn.commit()
        except Exception as e:
            app.logger.warning(f"Could not create task_embeddings table: {e}")

        # Create FTS5 virtual table for keyword search
        try:
            raw_conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5("
                "task_id UNINDEXED, title, description, tags_text"
                ")"
            )
            raw_conn.commit()
        except Exception as e:
            app.logger.warning(f"Could not create search_index table: {e}")

        raw_conn.close()


def get_vec_connection():
    """Get a database connection with sqlite-vec loaded.

    Creates a fresh connection each time to avoid lock conflicts with the ORM session.
    Caller is responsible for closing the connection.
    """
    from app.models import db

    conn = db.engine.raw_connection()
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except AttributeError:
        pass  # Extension loading not available
    return conn



