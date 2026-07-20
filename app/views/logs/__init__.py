from flask import Blueprint, g, redirect, render_template, request

from app.models import Log, Project, Task, db, scoped_get

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/projects/<int:project_id>/logs", methods=["POST"])
def create_project_log(project_id):
    project = scoped_get(Project, project_id, g.current_user)
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip() or None

    if not title:
        return redirect(request.referrer or "/")

    log = Log(title=title, notes=notes, project_id=project_id, user_id=g.current_user_id)
    db.session.add(log)
    db.session.commit()

    return redirect(request.referrer or "/")


@logs_bp.route("/tasks/<int:task_id>/logs", methods=["POST"])
def create_task_log(task_id):
    task = scoped_get(Task, task_id, g.current_user)
    title = request.form.get("title", "").strip()
    notes = request.form.get("notes", "").strip() or None

    if not title:
        return redirect(request.referrer or "/")

    log = Log(title=title, notes=notes, task_id=task_id, user_id=g.current_user_id)
    db.session.add(log)
    db.session.commit()

    return redirect(request.referrer or "/")


@logs_bp.route("/logs/<int:log_id>")
def log_detail(log_id):
    log = scoped_get(Log, log_id, g.current_user)
    return render_template("logs/detail.html", log=log)


@logs_bp.route("/logs/<int:log_id>", methods=["POST", "DELETE"])
def delete(log_id):
    # Handle POST with _method=DELETE (browsers can't send DELETE directly)
    if request.method == "POST" and request.form.get("_method") != "DELETE":
        return redirect(request.referrer or "/")
    log = scoped_get(Log, log_id, g.current_user)
    db.session.delete(log)
    db.session.commit()

    return redirect(request.referrer or "/")
