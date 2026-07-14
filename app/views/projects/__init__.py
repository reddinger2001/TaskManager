from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import text

from app.models import Project, Task, db

projects_bp = Blueprint("projects", __name__)

# Palette of 16 distinct colors for auto-assignment
_COLOR_PALETTE = [
    "#00e5ff", "#7c4dff", "#ff6ec7", "#ffd740",
    "#69f0ae", "#ff8a65", "#ba68c8", "#4dd0e1",
    "#aed581", "#ffb74d", "#e57373", "#81c784",
    "#64b5f6", "#f06292", "#ffca28", "#a1887f",
]


def _auto_color() -> str:
    """Pick the least-used color from the palette."""
    existing = db.session.query(Project.color).filter(Project.color.isnot(None)).all()
    counts = {}
    for (c,) in existing:
        counts[c] = counts.get(c, 0) + 1
    return min(_COLOR_PALETTE, key=lambda c: counts.get(c, 0))


@projects_bp.route("/projects")
def list_projects():
    from sqlalchemy import text

    # Single query with task_count and completion_pct computed in SQL
    results = db.session.execute(text("""
        SELECT
            p.id, p.name, p.description, p.color, p.parent_id,
            p.start_date, p.end_date, p.created_at, p.updated_at,
            COUNT(t.id) AS task_count,
            COALESCE(
                CAST(SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) * 100.0
                    / NULLIF(COUNT(t.id), 0) AS INTEGER),
                0
            ) AS completion_pct
        FROM projects p
        LEFT JOIN tasks t ON p.id = t.project_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)).fetchall()

    # Build Project objects from raw rows (template expects Project instances)
    projects = []
    for row in results:
        p = Project(id=row[0], name=row[1], description=row[2], color=row[3],
                     parent_id=row[4], start_date=row[5], end_date=row[6],
                     created_at=row[7], updated_at=row[8])
        p.task_count = row[9]
        p.completion_pct = row[10]
        projects.append(p)

    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/projects/new", methods=["POST"])
def create():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Project name is required", "error")
        return redirect(url_for("projects.list_projects"))

    parent_id = int(request.form["parent_id"]) if request.form.get("parent_id") else None

    project = Project(
        name=name,
        description=request.form.get("description", "").strip() or None,
        color=_auto_color(),
        start_date=request.form.get("start_date") or None,
        end_date=request.form.get("end_date") or None,
        parent_id=parent_id,
    )
    db.session.add(project)
    db.session.commit()
    flash(f"Project \"{name}\" created")
    return redirect(url_for("projects.detail", project_id=project.id))


@projects_bp.route("/projects/<int:project_id>")
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    # Include tasks from this project and all child projects
    descendant_ids = project.get_descendant_ids()
    tasks = Task.query.filter(
        Task.project_id.in_(descendant_ids),
    ).order_by(Task.created_at.desc()).all()

    # FTS5-based related captures (inbox tasks matching this project's content)
    from app.views.tasks import _find_related_captures
    search_text = project.name
    if project.description:
        search_text += " " + project.description
    related_captures = _find_related_captures(search_text)

    all_projects = Project.query.order_by(Project.name.asc()).all()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return render_template("projects/detail.html", project=project, tasks=tasks, related_captures=related_captures, all_projects=all_projects, today_str=today_str)


@projects_bp.route("/projects/<int:project_id>", methods=["PATCH"])
def update(project_id):
    project = Project.query.get_or_404(project_id)
    data = request.get_json(silent=True) or {}

    if "name" in data:
        project.name = data["name"].strip()
    if "description" in data:
        project.description = data["description"].strip() or None
    if "color" in data:
        project.color = data["color"] or None
    if "start_date" in data:
        project.start_date = data["start_date"] or None
    if "end_date" in data:
        project.end_date = data["end_date"] or None
    if "parent_id" in data:
        new_parent_id = int(data["parent_id"]) if data["parent_id"] else None
        # Prevent circular references: can't set parent to self or a descendant
        if new_parent_id and project.is_ancestor_of(Project.query.get(new_parent_id)):
            return {"ok": False, "error": "Cannot set parent — would create a circular reference"}, 400
        project.parent_id = new_parent_id

    db.session.commit()
    return {"ok": True}


@projects_bp.route("/projects/<int:project_id>", methods=["DELETE", "POST"])
def delete(project_id):
    # Accept POST with _method=DELETE for browser form submissions
    if request.method == "POST":
        _method = request.form.get("_method", "").upper()
        if _method != "DELETE":
            return redirect(url_for("projects.detail", project_id=project_id))

    project = Project.query.get_or_404(project_id)
    name = project.name
    db.session.delete(project)
    db.session.commit()
    flash(f"Project \"{name}\" deleted")
    return redirect(url_for("projects.list_projects"))
