#!/usr/bin/env python3
"""Migration script to add multi-user support to an existing TaskManager database.

Creates the users table, adds user_id FK columns to tasks/projects/logs,
creates an admin user, and backfills all existing rows to that admin.

Usage:
    python scripts/migrate_multi_user.py

This is a one-time migration. Run it once before deploying the multi-user code.
"""

import pysqlite3 as sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "/Volumes/DevEnvironment/projects/TaskManager/instance/taskmanager.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create users table
    print("Creating users table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Create admin user
    print("Creating admin user...")
    cursor.execute(
        "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, CURRENT_TIMESTAMP)",
        ("admin", generate_password_hash("admin")),
    )
    admin_id = cursor.lastrowid
    print(f"  Admin user created with id={admin_id}")

    # 3. Add user_id to projects (nullable first)
    print("Adding user_id to projects...")
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("  Column already exists, skipping")
        else:
            raise

    # 4. Backfill projects.user_id
    print("Backfilling projects.user_id...")
    cursor.execute("UPDATE projects SET user_id = ? WHERE user_id IS NULL", (admin_id,))

    # 5. Add user_id to tasks (nullable first)
    print("Adding user_id to tasks...")
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("  Column already exists, skipping")
        else:
            raise

    # 6. Backfill tasks.user_id
    print("Backfilling tasks.user_id...")
    cursor.execute("UPDATE tasks SET user_id = ? WHERE user_id IS NULL", (admin_id,))

    # 7. Add user_id to logs (nullable first)
    print("Adding user_id to logs...")
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN user_id INTEGER REFERENCES users(id)")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("  Column already exists, skipping")
        else:
            raise

    # 8. Backfill logs.user_id
    print("Backfilling logs.user_id...")
    cursor.execute("UPDATE logs SET user_id = ? WHERE user_id IS NULL", (admin_id,))

    # 9. Add shared_with to projects
    print("Adding shared_with to projects...")
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN shared_with TEXT")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("  Column already exists, skipping")
        else:
            raise

    conn.commit()

    # Verify
    print("\nVerification:")
    cursor.execute("SELECT COUNT(*) FROM users")
    print(f"  Users: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM projects WHERE user_id IS NOT NULL")
    print(f"  Projects with user_id: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id IS NOT NULL")
    print(f"  Tasks with user_id: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM logs WHERE user_id IS NOT NULL")
    print(f"  Logs with user_id: {cursor.fetchone()[0]}")

    conn.close()
    print("\nMigration complete! Login with username: admin, password: admin")
    print("Change the password immediately after logging in.")

if __name__ == "__main__":
    migrate()
