"""Auto-migration for multi-user support.

Runs automatically on app startup if the database is missing the users table
or user_id columns. Creates an admin user and backfills existing rows.

This handles the upgrade path from solo-mode TaskManager to multi-user.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def migrate_multi_user(app):
    """Migrate an existing database to support multi-user.

    Only runs if needed — checks for the users table and user_id columns.
    Creates admin user with username "admin" and password "admin" (printed to console).
    """
    from app.models import User, db

    with app.app_context():
        raw_conn = db.engine.raw_connection()

        # Check if users table exists
        tables = [row[0] for row in raw_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]

        if "users" in tables:
            raw_conn.close()
            return  # Already migrated

        logger.info("Multi-user migration detected — migrating database...")

        # 1. Create users table
        raw_conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(256) NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Create admin user
        from werkzeug.security import generate_password_hash
        raw_conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, CURRENT_TIMESTAMP)",
            ("admin", generate_password_hash("admin")),
        )
        admin_id = raw_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 3. Add user_id to projects
        try:
            raw_conn.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER REFERENCES users(id)")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                raise

        # 4. Backfill projects.user_id
        raw_conn.execute("UPDATE projects SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # 5. Add user_id to tasks
        try:
            raw_conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER REFERENCES users(id)")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                raise

        # 6. Backfill tasks.user_id
        raw_conn.execute("UPDATE tasks SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # 7. Add user_id to logs
        try:
            raw_conn.execute("ALTER TABLE logs ADD COLUMN user_id INTEGER REFERENCES users(id)")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                raise

        # 8. Backfill logs.user_id
        raw_conn.execute("UPDATE logs SET user_id = ? WHERE user_id IS NULL", (admin_id,))

        # 9. Add shared_with to projects
        try:
            raw_conn.execute("ALTER TABLE projects ADD COLUMN shared_with TEXT")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass
            else:
                raise

        raw_conn.commit()
        raw_conn.close()

        logger.info(
            "Multi-user migration complete! Login with username: admin, password: admin. "
            "Change the password immediately after logging in."
        )
