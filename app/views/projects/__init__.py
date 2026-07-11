from flask import Blueprint, flash, redirect, render_template, request, url_for

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
    projects = Project.query.order_by(Project.created_at.desc()).all()
    for p in projects:
        p.task_count = len(p.tasks)
        done = sum(1 for t in p.tasks if t.status == "done")
        p.completion_pct = int(done / p.task_count * 100) if p.task_count else 0
    return render_template("projects/list.html", projects=projects)


@projects_bp.route("/projects/new", methods=["POST"])
def create():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Project name is required", "error")
        return redirect(url_for("projects.list_projects"))

    project = Project(
        name=name,
        description=request.form.get("description", "").strip() or None,
        color=_auto_color(),
        parent_id=int(request.form["parent_id"]) if request.form.get("parent_id") else None,
    )
    db.session.add(project)
    db.session.commit()
    flash(f"Project \"{name}\" created")
    return redirect(url_for("projects.detail", project_id=project.id))


@projects_bp.route("/projects/<int:project_id>")
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.created_at.desc()).all()
    return render_template("projects/detail.html", project=project, tasks=tasks)


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
    if "parent_id" in data:
        project.parent_id = int(data["parent_id"]) if data["parent_id"] else None

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
