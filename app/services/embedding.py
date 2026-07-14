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

# Queue of (task_id, title, description, tags_text) to index in FTS5 after commit.
_pending_fts5: List[tuple] = []


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


def search_similar(query_text: str, limit: int = 5, exclude_ids: List[int] | None = None) -> List[tuple]:
    """Search for tasks similar to the query text using cosine similarity.

    Returns list of (task_id, distance) tuples sorted by relevance (closest first).
    Distance is cosine distance — lower means more similar (0 = identical, 1 = opposite).
    """
    from app.extensions import get_vec_connection

    vec = embed(query_text)
    vec_json = json.dumps(vec)

    conn = get_vec_connection()
    try:
        sql = "SELECT task_id, distance FROM task_embeddings WHERE embedding MATCH ? LIMIT ?"
        params = [vec_json, limit]

        rows = conn.execute(sql, params).fetchall()
        results = [(row[0], row[1]) for row in rows]

        # Filter out excluded IDs
        if exclude_ids:
            results = [(tid, dist) for tid, dist in results if tid not in set(exclude_ids)]

        return results
    except Exception:
        logger.exception("Failed to search embeddings")
        return []
    finally:
        conn.close()


def hybrid_search(query_text: str, limit: int = 50, semantic_weight: float = 0.6) -> List[tuple]:
    """Combine FTS5 keyword results with sqlite-vec semantic results.

    Returns list of (task_id, combined_score) tuples sorted by relevance.
    Score is normalized to 0-1 range where 1 = most relevant.
    """
    from app.extensions import get_vec_connection

    # --- Keyword search via FTS5 ---
    keyword_map = {}  # task_id -> normalized_rank (0-1)
    try:
        conn = get_vec_connection()
        cursor = conn.execute(
            "SELECT task_id, rank FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT ?",
            (query_text, limit),
        )
        rows = cursor.fetchall()
        if rows:
            ranks = [row[1] for row in rows]
            min_rank = min(ranks)
            max_rank = max(ranks)
            rank_range = max_rank - min_rank if max_rank != min_rank else 1.0
            for row in rows:
                # FTS5 rank is negative — lower (more negative) = more relevant
                normalized = 1.0 - ((row[1] - min_rank) / rank_range)
                keyword_map[row[0]] = normalized
        conn.close()
    except Exception:
        logger.exception("FTS5 search failed in hybrid_search")

    # --- Semantic search via sqlite-vec ---
    semantic_map = {}  # task_id -> normalized_score (0-1)
    try:
        vec = embed(query_text)
        vec_json = json.dumps(vec)
        conn = get_vec_connection()
        rows = conn.execute(
            "SELECT task_id, distance FROM task_embeddings WHERE embedding MATCH ? LIMIT ?",
            (vec_json, limit),
        ).fetchall()
        if rows:
            distances = [row[1] for row in rows]
            min_dist = min(distances)
            max_dist = max(distances)
            dist_range = max_dist - min_dist if max_dist != min_dist else 1.0
            for row in rows:
                # distance 0 = perfect match, normalize so 0 -> 1.0
                normalized = 1.0 - ((row[1] - min_dist) / dist_range)
                semantic_map[row[0]] = normalized
        conn.close()
    except Exception:
        logger.exception("Semantic search failed in hybrid_search")

    # --- Combine scores ---
    all_ids = set(keyword_map.keys()) | set(semantic_map.keys())
    results = []
    for task_id in all_ids:
        kw_score = keyword_map.get(task_id, 0.0)
        sem_score = semantic_map.get(task_id, 0.0)
        combined = (1 - semantic_weight) * kw_score + semantic_weight * sem_score
        results.append((task_id, round(combined, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


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


def backfill_fts5():
    """Backfill FTS5 index for all existing tasks.

    Called once at app startup. Clears the index first to avoid duplicates
    from repeated runs.
    """
    from app.extensions import get_vec_connection
    from app.models import Task, db

    try:
        conn = get_vec_connection()
        # Clear existing index to avoid duplicates
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
        logger.info("FTS5 backfill complete: %d tasks indexed", len(tasks))
    except Exception:
        logger.exception("FTS5 backfill failed")
    finally:
        if 'conn' in dir():
            conn.close()


def register_fts5_hooks(app):
    """Register SQLAlchemy event hooks to keep FTS5 search_index in sync.

    Uses after_flush to queue tasks (IDs are assigned), then after_commit
    to actually write to the FTS5 virtual table (DB is free of locks).
    """
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


def _flush_fts5():
    """Process all pending FTS5 index updates."""
    global _pending_fts5
    tasks = list(_pending_fts5)
    _pending_fts5.clear()

    if not tasks:
        return

    try:
        from app.extensions import get_vec_connection

        conn = get_vec_connection()
        try:
            for task_id, title, description, tags_text in tasks:
                # Delete old row first — FTS5 doesn't support REPLACE on non-UNINDEXED columns
                conn.execute("DELETE FROM search_index WHERE task_id = ?", (task_id,))
                conn.execute(
                    "INSERT INTO search_index(task_id, title, description, tags_text) VALUES (?, ?, ?, ?)",
                    (task_id, title, description, tags_text),
                )
            conn.commit()
        except Exception:
            logger.exception("Failed to sync FTS5 index")
        finally:
            conn.close()
    except Exception:
        logger.exception("FTS5 sync: could not get connection")
