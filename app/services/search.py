"""FTS5 search index management.

Keeps the FTS5 virtual table in sync with Task records via SQLAlchemy event hooks.
"""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)

# Queue of (task_id, title, description, tags_text) to index after commit.
_pending_fts5: List[tuple] = []


def register_fts5_hooks(app):
    """Register SQLAlchemy event hooks to keep FTS5 search_index in sync."""
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.models import Task

    # Backfill existing tasks on startup
    with app.app_context():
        backfill_fts5()

    @event.listens_for(Session, "after_flush")
    def _on_flush(session, flush_context):
        for obj in session.new | session.dirty:
            if isinstance(obj, Task) and obj.id is not None:
                tags_text = " ".join(obj.get_tags()) if obj.tags else ""
                _pending_fts5.append((obj.id, obj.title or "", obj.description or "", tags_text))

    @event.listens_for(Session, "after_commit")
    def _on_commit(session):
        _flush_fts5()


def backfill_fts5():
    """Backfill FTS5 index for all existing tasks."""
    from app.models import Task, db

    try:
        conn = db.engine.raw_connection()
        conn.execute("DELETE FROM search_index")
        conn.commit()

        tasks = db.session.query(Task).all()
        for task in tasks:
            tags_text = " ".join(task.get_tags()) if task.tags else ""
            conn.execute(
                "INSERT INTO search_index(task_id, title, description, tags_text) VALUES (?, ?, ?, ?)",
                (task.id, task.title or "", task.description or "", tags_text),
            )
        conn.commit()
    except Exception:
        logger.exception("FTS5 backfill failed")


def _flush_fts5():
    """Process all pending FTS5 index updates."""
    global _pending_fts5
    tasks = list(_pending_fts5)
    _pending_fts5.clear()

    if not tasks:
        return

    try:
        from app.models import db

        conn = db.engine.raw_connection()
        for task_id, title, description, tags_text in tasks:
            conn.execute("DELETE FROM search_index WHERE task_id = ?", (task_id,))
            conn.execute(
                "INSERT INTO search_index(task_id, title, description, tags_text) VALUES (?, ?, ?, ?)",
                (task_id, title, description, tags_text),
            )
        conn.commit()
    except Exception:
        logger.exception("FTS5 flush failed")
