"""Embedding generation using sentence-transformers.

Generates 384-dim float vectors using the all-MiniLM-L6-v2 model for semantic
search via sqlite-vec. Caches the model instance globally so it is loaded only
once per process.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import List

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Return the singleton embedding model, loading it on first call."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(text: str) -> List[float]:
    """Generate a 384-dim embedding for the given text.

    Args:
        text: The text to embed.

    Returns:
        List of 384 floats representing the embedding vector.
    """
    vec = get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of texts."""
    if not texts:
        return []
    vecs = get_model().encode(texts, normalize_embeddings=True)
    return vecs.tolist()


def _store_embedding(app_ctx, task_id: int, text: str):
    """Store the embedding vector for a task in sqlite-vec.

    Called in a background thread after commit. Silently swallows errors —
    embedding is a best-effort operation.
    """
    from app.extensions import get_vec_connection

    text = (text or "").strip()
    if not text:
        return

    with app_ctx:
        try:
            vec = embed(text)
            conn = get_vec_connection()
            try:
                # Upsert: delete old row first, then insert
                conn.execute("DELETE FROM task_embeddings WHERE task_id = ?", (task_id,))
                conn.execute(
                    "INSERT INTO task_embeddings(task_id, embedding) VALUES (?, ?)",
                    (task_id, json.dumps(vec)),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("Failed to generate/store embedding for task %d", task_id)


def queue_embedding(app_ctx, task_id: int, title: str, description: str | None = None):
    """Queue an embedding job for a task in a background thread.

    Concatenates title and description (if present) as the text to embed.
    The model is loaded lazily on first use — no startup cost.
    """
    text = title.strip()
    if description:
        text += " " + description.strip()

    if not text or task_id is None:
        return

    thread = threading.Thread(target=_store_embedding, args=(app_ctx, task_id, text), daemon=True)
    thread.start()


def warmup_model():
    """Pre-load the embedding model so background threads don't segfault.

    sentence-transformers + PyTorch can crash when loading the model
    concurrently from multiple threads. Load it once in the main thread
    at app startup.
    """
    logger.info("Warming up embedding model (%s) ...", MODEL_NAME)
    get_model()
    logger.info("Embedding model ready")


def register_embedding_hooks(app):
    """Register SQLAlchemy event hooks to trigger embedding on task save.

    Listens for `after_flush` events — IDs are assigned at this point but the
    transaction is still open. Embedding runs in a background thread so it
    doesn't block the request.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.models import Task

    # Warm up the model in the main thread before any background threads run
    warmup_model()

    app_ctx = app.app_context()
    app_ctx.push()

    @event.listens_for(Session, "after_flush")
    def _on_flush(session, flush_context):
        for obj in session.new | session.dirty:
            if isinstance(obj, Task):
                queue_embedding(app_ctx, obj.id, obj.title, obj.description)
