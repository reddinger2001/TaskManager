"""Embedding generation using sentence-transformers.

Generates 384-dim float vectors using the all-MiniLM-L6-v2 model for semantic
search via sqlite-vec. Caches the model instance globally so it is loaded only
once per process.
"""

from __future__ import annotations

import json
import logging
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None

# Queue of (task_id, title, description) to embed after commit.
_pending_embeddings: List[tuple] = []


def get_model() -> SentenceTransformer:
    """Return the singleton embedding model, loading it on first call."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(text: str) -> List[float]:
    """Generate a 384-dim embedding for the given text."""
    vec = get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    if not texts:
        return []
    vecs = get_model().encode(texts, normalize_embeddings=True)
    return vecs.tolist()


def _flush_pending():
    """Process all pending embeddings. Called after commit when DB is free."""
    global _pending_embeddings
    tasks = list(_pending_embeddings)
    _pending_embeddings.clear()

    if not tasks:
        return

    from app.extensions import get_vec_connection

    conn = get_vec_connection()
    try:
        for task_id, title, description in tasks:
            text = title.strip()
            if description:
                text += " " + description.strip()
            if not text or task_id is None:
                continue

            try:
                vec = embed(text)
                conn.execute("DELETE FROM task_embeddings WHERE task_id = ?", (task_id,))
                conn.execute(
                    "INSERT INTO task_embeddings(task_id, embedding) VALUES (?, ?)",
                    (task_id, json.dumps(vec)),
                )
            except Exception:
                logger.exception("Failed to generate/store embedding for task %d", task_id)
        conn.commit()
    except Exception:
        logger.exception("Failed to flush embeddings batch")
    finally:
        conn.close()


def warmup_model():
    """Pre-load the embedding model in the main thread."""
    logger.info("Warming up embedding model (%s) ...", MODEL_NAME)
    get_model()
    logger.info("Embedding model ready")


def register_embedding_hooks(app):
    """Register SQLAlchemy event hooks to trigger embedding on task save.

    Uses after_flush to queue tasks (IDs are assigned), then after_commit
    to actually write embeddings (DB is free of locks).
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.models import Task

    warmup_model()

    @event.listens_for(Session, "after_flush")
    def _on_flush(session, flush_context):
        for obj in session.new | session.dirty:
            if isinstance(obj, Task):
                _pending_embeddings.append((obj.id, obj.title, obj.description))

    @event.listens_for(Session, "after_commit")
    def _on_commit(session):
        _flush_pending()
