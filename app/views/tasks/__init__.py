from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.models import Project, Task, db

tasks_bp = Blueprint("tasks", __name__)

STATUSES = ["backlog", "active", "blocked", "delegated", "done"]
PRIORITIES = ["P0", "P1", "P2"]

# Columns that can be sorted server-side
SORT_FIELDS = {
    "title": Task.title,
    "status": Task.status,
    "priority": Task.priority,
    "due_date": Task.due_date,
    "assignee": Task.assignee,
    "project": Project.name,
    "created_at": Task.created_at,
}

# Default sort: newest first
DEFAULT_SORT = ("created_at", "desc")


@tasks_bp.route("/tasks")
def list_tasks():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    project_id = request.args.get("project_id", "")
    assignee = request.args.get("assignee", "").strip()
    tag = request.args.get("tag", "").strip()
    date_field = request.args.get("date_field", "due_date")  # due_date, completed_at, created_at
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    # Sorting
    sort_field = request.args.get("sort", DEFAULT_SORT[0])
    sort_order = request.args.get("order", DEFAULT_SORT[1]).lower()
    if sort_field not in SORT_FIELDS:
        sort_field = DEFAULT_SORT[0]
    if sort_order not in ("asc", "desc"):
        sort_order = DEFAULT_SORT[1]

    query = Task.query.outerjoin(Project, Task.project_id == Project.id)

    # Filters
    if q:
        query = query.filter(Task.title.ilike(f"%{q}%"))
    if status and status in STATUSES:
        query = query.filter(Task.status == status)
    if priority and priority in PRIORITIES:
        query = query.filter(Task.priority == priority)
    if project_id:
        query = query.filter(Task.project_id == int(project_id))
    if assignee:
        query = query.filter(Task.assignee.ilike(f"%{assignee}%"))
    if tag:
        # Filter by JSON array contains the tag (case-insensitive via SQLite)
        query = query.filter(Task.tags.contains(f'"{tag}"'))
    # Date range filter — choose which date field to filter on
    DATE_FIELDS = {
        "due_date": Task.due_date,
        "completed_at": Task.completed_at,
        "created_at": Task.created_at,
    }
    if date_field in DATE_FIELDS and (date_from or date_to):
        col = DATE_FIELDS[date_field]
        if date_from:
            query = query.filter(col >= date_from)
        if date_to:
            query = query.filter(col <= date_to)

    # Sorting — nulls last for nullable columns
    sort_col = SORT_FIELDS[sort_field]
    if sort_order == "desc":
        sort_col = sort_col.desc()

    tasks = query.order_by(sort_col, Task.created_at.desc()).all()

    # Gather filter options
    projects = Project.query.order_by(Project.name).all()
    assignees = (
        db.session.query(Task.assignee)
        .filter(Task.assignee.isnot(None))
        .distinct()
        .order_by(Task.assignee.asc())
        .all()
    )
    assignees = [a[0] for a in assignees]

    # All unique tags across tasks (for filter dropdown)
    all_tags = set()
    for t in tasks:
        if t.tags:
            all_tags.update(t.tags)
    all_tags = sorted(all_tags)

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        projects=projects,
        statuses=STATUSES,
        priorities=PRIORITIES,
        assignees=assignees,
        all_tags=all_tags,
        current_q=q,
        current_status=status,
        current_priority=priority,
        current_project_id=project_id,
        current_assignee=assignee,
        current_tag=tag,
        current_date_field=date_field,
        current_date_from=date_from,
        current_date_to=date_to,
        sort_field=sort_field,
        sort_order=sort_order,
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

    # Semantic search — find related inbox items
    related_captures = []
    try:
        from app.services.embedding import search_similar

        query_text = task.title
        if task.description:
            query_text += " " + task.description

        similar = search_similar(query_text, limit=5, exclude_ids=[task.id])

        if similar:
            # Filter out low-similarity results
            similar = [(tid, dist) for tid, dist in similar if dist < 1.2]
            if similar:
                task_ids = [tid for tid, _ in similar]
                related_captures = Task.query.filter(
                    Task.id.in_(task_ids),
                    Task.project_id.is_(None),  # inbox items only
                ).all()
                id_order = {tid: i for i, tid in enumerate(task_ids)}
                related_captures.sort(key=lambda t: id_order.get(t.id, 999))
    except Exception:
        pass  # Graceful fallback

    return render_template(
        "tasks/detail.html",
        task=task,
        projects=projects,
        statuses=STATUSES,
        priorities=PRIORITIES,
        related_captures=related_captures,
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
    if "links" in data:
        task.set_links(data["links"])

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
