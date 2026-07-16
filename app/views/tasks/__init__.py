import csv
import io
from datetime import date, datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from app.models import Project, Task, db

tasks_bp = Blueprint("tasks", __name__)

STATUSES = ["backlog", "active", "blocked", "delegated", "done"]
PRIORITIES = ["P0", "P1", "P2"]
RECURRENCES = ["", "daily", "weekly", "monthly"]

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


def build_task_query():
    """Build a filtered/sorted Task query from the current request args.

    Shared by list_tasks and export_csv to avoid duplicating ~60 lines of logic.
    Returns (query, sort_field, sort_order) tuple.
    """
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    project_id = request.args.get("project_id", "")
    assignee = request.args.get("assignee", "").strip()
    tag = request.args.get("tag", "").strip()
    date_field = request.args.get("date_field", "due_date")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    sort_field = request.args.get("sort", DEFAULT_SORT[0])
    sort_order = request.args.get("order", DEFAULT_SORT[1]).lower()
    if sort_field not in SORT_FIELDS:
        sort_field = DEFAULT_SORT[0]
    if sort_order not in ("asc", "desc"):
        sort_order = DEFAULT_SORT[1]

    query = Task.query.outerjoin(Project, Task.project_id == Project.id)

    if q:
        query = query.filter(Task.title.ilike(f"%{q}%"))
    if status and status in STATUSES:
        query = query.filter(Task.status == status)
    elif status == "inbox":
        query = query.filter(Task.project_id.is_(None))
    if priority and priority in PRIORITIES:
        query = query.filter(Task.priority == priority)
    if project_id:
        query = query.filter(Task.project_id == int(project_id))
    if assignee:
        query = query.filter(Task.assignee.ilike(f"%{assignee}%"))
    if tag:
        query = query.filter(Task.tags.contains(f'"{tag}"'))

    DATE_FIELDS = {
        "due_date": Task.due_date,
        "completed_at": Task.completed_at,
        "created_at": Task.created_at,
    }
    if date_field in DATE_FIELDS and (date_from or date_to):
        col = DATE_FIELDS[date_field]
        if date_from:
            query = query.filter(col >= date.fromisoformat(date_from))
        if date_to:
            query = query.filter(col <= date.fromisoformat(date_to))

    sort_col = SORT_FIELDS[sort_field]
    if sort_order == "desc":
        sort_col = sort_col.desc()

    return query.order_by(sort_col, Task.created_at.desc()), sort_field, sort_order


@tasks_bp.route("/tasks")
def list_tasks():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    project_id = request.args.get("project_id", "")
    assignee = request.args.get("assignee", "").strip()
    tag = request.args.get("tag", "").strip()
    date_field = request.args.get("date_field", "due_date")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query, sort_field, sort_order = build_task_query()

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    if per_page < 1 or per_page > 200:
        per_page = 50
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tasks = pagination.items

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
        pagination=pagination,
        projects=projects,
        statuses=STATUSES,
        priorities=PRIORITIES,
        assignees=assignees,
        all_tags=all_tags,
        today_date=date.today(),
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


@tasks_bp.route("/tasks/export.csv")
def export_csv():
    """Export task list as CSV, applying current filters."""
    query, _sort_field, _sort_order = build_task_query()
    tasks = query.all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Status", "Priority", "Assignee", "Due Date", "Project", "Tags"])
    for t in tasks:
        writer.writerow([
            t.title,
            t.status,
            t.priority or "",
            t.assignee or "",
            t.due_date or "",
            t.project.name if t.project else "",
            ", ".join(t.get_tags()),
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="tasks.csv",
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
        start_date=date.fromisoformat(request.form["start_date"]) if request.form.get("start_date") else None,
        due_date=date.fromisoformat(request.form["due_date"]) if request.form.get("due_date") else None,
        assignee=request.form.get("assignee", "").strip() or None,
        project_id=int(request.form["project_id"]) if request.form.get("project_id") else None,
        recurrence=request.form.get("recurrence") or None,
        recurrence_end=date.fromisoformat(request.form["recurrence_end"]) if request.form.get("recurrence_end") else None,
    )

    # Handle tags from comma-separated input
    tags_raw = request.form.get("tags", "").strip()
    if tags_raw:
        task.set_tags([t.strip() for t in tags_raw.split(",") if t.strip()])

    db.session.add(task)
    db.session.commit()
    flash(f"Task \"{title}\" created")
    return redirect(url_for("tasks.detail", task_id=task.id))


def _find_related_captures(query_text, exclude_ids=None, limit=5):
    """Find related inbox tasks via FTS5 keyword search.

    Searches the FTS5 index for tasks matching the query text,
    scoped to inbox items (no project assigned) and excluding given IDs.
    Falls back to empty list if FTS5 fails.
    """
    from app.extensions import get_vec_connection

    try:
        conn = get_vec_connection()
        rows = conn.execute(
            "SELECT task_id FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT ?",
            (query_text, limit),
        ).fetchall()
        conn.close()

        if not rows:
            return []

        task_ids = [r[0] for r in rows]
        if exclude_ids:
            task_ids = [tid for tid in task_ids if tid not in set(exclude_ids)]

        return Task.query.filter(
            Task.id.in_(task_ids),
            Task.project_id.is_(None),
        ).all()
    except Exception:
        return []


@tasks_bp.route("/tasks/<int:task_id>")
def detail(task_id):
    task = Task.query.get_or_404(task_id)
    projects = Project.query.order_by(Project.name).all()
    assignees = sorted(set(t.assignee for t in Task.query.filter(Task.assignee.isnot(None)).all() if t.assignee))

    # FTS5-based related captures (inbox tasks matching this task's content)
    search_text = task.title
    if task.description:
        search_text += " " + task.description
    related_captures = _find_related_captures(search_text, exclude_ids=[task.id])

    # All tasks for the dependency dropdown (exclude self)
    all_tasks = Task.query.filter(Task.id != task.id).order_by(Task.title).all()

    return render_template(
        "tasks/detail.html",
        task=task,
        projects=projects,
        assignees=assignees,
        statuses=STATUSES,
        priorities=PRIORITIES,
        recurrences=RECURRENCES,
        related_captures=related_captures,
        all_tasks=all_tasks,
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
    if "start_date" in data:
        task.start_date = date.fromisoformat(data["start_date"]) if data["start_date"] else None
    if "due_date" in data:
        task.due_date = date.fromisoformat(data["due_date"]) if data["due_date"] else None
    if "recurrence" in data:
        task.recurrence = data["recurrence"] or None
    if "recurrence_end" in data:
        task.recurrence_end = date.fromisoformat(data["recurrence_end"]) if data["recurrence_end"] else None
    if "assignee" in data:
        task.assignee = data["assignee"].strip() or None
    if "project_id" in data:
        task.project_id = int(data["project_id"]) if data["project_id"] else None
    if "tags" in data:
        task.set_tags(data["tags"])
    if "links" in data:
        task.set_links(data["links"])
    if "depends_on_id" in data:
        new_dep = data["depends_on_id"]
        if new_dep:
            new_dep = int(new_dep)
            if new_dep == task.id:
                return {"error": "A task cannot depend on itself"}, 400
            dep_task = Task.query.get(new_dep)
            if not dep_task:
                return {"error": "Dependency task not found"}, 404
            if task.would_create_cycle(new_dep):
                return {"error": "This would create a circular dependency"}, 400
        task.depends_on_id = new_dep or None

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
