from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.models import Project, Task, db

tasks_bp = Blueprint("tasks", __name__)

STATUSES = ["backlog", "active", "blocked", "delegated", "done"]
PRIORITIES = ["P0", "P1", "P2"]


@tasks_bp.route("/tasks")
def list_tasks():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    project_id = request.args.get("project_id", "")

    query = Task.query

    if q:
        query = query.filter(Task.title.ilike(f"%{q}%"))
    if status and status in STATUSES:
        query = query.filter_by(status=status)
    if priority and priority in PRIORITIES:
        query = query.filter_by(priority=priority)
    if project_id:
        query = query.filter_by(project_id=int(project_id))

    tasks = query.order_by(Task.created_at.desc()).all()
    projects = Project.query.order_by(Project.name).all()

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        projects=projects,
        statuses=STATUSES,
        priorities=PRIORITIES,
        current_q=q,
        current_status=status,
        current_priority=priority,
        current_project_id=project_id,
    )


@tasks_bp.route("/tasks/new", methods=["POST"])
def create():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required", "error")
        return redirect(url_for("tasks.list_tasks"))

    task = Task(
        title=title,
        description=request.form.get("description", "").strip() or None,
        status=request.form.get("status", "backlog") or "backlog",
        priority=request.form.get("priority") or None,
        due_date=request.form.get("due_date") or None,
        assignee=request.form.get("assignee", "").strip() or None,
        project_id=int(request.form["project_id"]) if request.form.get("project_id") else None,
    )

    # Handle tags from comma-separated input
    tags_raw = request.form.get("tags", "").strip()
    if tags_raw:
        task.set_tags([t.strip() for t in tags_raw.split(",") if t.strip()])

    db.session.add(task)
    db.session.commit()
    flash(f"Task \"{title}\" created")
    return redirect(url_for("tasks.detail", task_id=task.id))


@tasks_bp.route("/tasks/<int:task_id>")
def detail(task_id):
    task = Task.query.get_or_404(task_id)
    projects = Project.query.order_by(Project.name).all()
    return render_template(
        "tasks/detail.html",
        task=task,
        projects=projects,
        statuses=STATUSES,
        priorities=PRIORITIES,
    )


@tasks_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
def update(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json(silent=True) or {}

    old_status = task.status
    new_status = data.get("status", old_status)

    if "title" in data:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = data["description"].strip() or None
    if "status" in data:
        task.status = new_status
    if "priority" in data:
        task.priority = data["priority"] or None
    if "due_date" in data:
        task.due_date = data["due_date"] or None
    if "assignee" in data:
        task.assignee = data["assignee"].strip() or None
    if "project_id" in data:
        task.project_id = int(data["project_id"]) if data["project_id"] else None
    if "tags" in data:
        task.set_tags(data["tags"])

    # Handle status transitions
    if new_status == "done" and old_status != "done":
        task.completed_at = datetime.now(timezone.utc)
    elif new_status != "done" and old_status == "done":
        task.completed_at = None

    db.session.commit()
    return {"ok": True}


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE", "POST"])
def delete(task_id):
    if request.method == "POST":
        _method = request.form.get("_method", "").upper()
        if _method != "DELETE":
            return redirect(url_for("tasks.detail", task_id=task_id))

    task = Task.query.get_or_404(task_id)
    title = task.title
    db.session.delete(task)
    db.session.commit()
    flash(f"Task \"{title}\" deleted")
    return redirect(url_for("tasks.list_tasks"))
