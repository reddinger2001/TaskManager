from flask import Blueprint, redirect, request

from app.extensions import get_vec_connection
from app.models import Log, Project, Task, db

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/projects/<int:project_id>/logs", methods=["POST"])
def create_project_log(project_id):
    project = Project.query.get_or_404(project_id)
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip() or None

    if not title:
        return redirect(request.referrer or "/")

    log = Log(title=title, notes=notes, project_id=project_id)
    db.session.add(log)
    db.session.commit()

    # Update FTS5 index
    try:
        conn = get_vec_connection()
        conn.execute(
            "INSERT INTO search_index(rowid, content) VALUES (?, ?)",
            (log.id, f"{log.title} {log.notes or ''}"),
        )
        conn.commit()
    except Exception:
        pass

    return redirect(request.referrer or "/")


@logs_bp.route("/tasks/<int:task_id>/logs", methods=["POST"])
def create_task_log(task_id):
    task = Task.query.get_or_404(task_id)
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip() or None

    if not title:
        return redirect(request.referrer or "/")

    log = Log(title=title, notes=notes, task_id=task_id)
    db.session.add(log)
    db.session.commit()

    # Update FTS5 index
    try:
        conn = get_vec_connection()
        conn.execute(
            "INSERT INTO search_index(rowid, content) VALUES (?, ?)",
            (log.id, f"{log.title} {log.notes or ''}"),
        )
        conn.commit()
    except Exception:
        pass

    return redirect(request.referrer or "/")


@logs_bp.route("/logs/<int:log_id>", methods=["POST", "DELETE"])
def delete(log_id):
    # Handle POST with _method=DELETE (browsers can't send DELETE directly)
    if request.method == "POST" and request.form.get("_method") != "DELETE":
        return redirect(request.referrer or "/")
    log = Log.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()

    # Remove from FTS5
    try:
        conn = get_vec_connection()
        conn.execute("DELETE FROM search_index WHERE rowid = ?", (log_id,))
        conn.commit()
    except Exception:
        pass

    return redirect(request.referrer or "/")
