import re

from flask import Blueprint, current_app as app, request, render_template
from markupsafe import Markup

from app.models import Log, Project, Task, db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    # On Fire: P0 tasks + all blocked tasks
    on_fire = (
        db.session.query(Task)
        .filter(db.or_(Task.priority == "P0", Task.status == "blocked"))
        .order_by(
            db.case((Task.priority == "P0", 0), else_=1),
            Task.created_at.desc(),
        )
        .all()
    )

    # Delegated: tasks with status=delegated, grouped by assignee
    delegated = (
        db.session.query(Task)
        .filter(Task.status == "delegated")
        .order_by(Task.assignee, Task.created_at.desc())
        .all()
    )

    # Active: tasks with status=active
    active = (
        db.session.query(Task)
        .filter(Task.status == "active")
        .order_by(Task.created_at.desc())
        .all()
    )

    # Backlog: tasks with status=backlog, sorted by priority then due date
    backlog = (
        db.session.query(Task)
        .filter(Task.status == "backlog")
        .order_by(
            db.case(
                (Task.priority == "P1", 0),
                (Task.priority == "P2", 1),
                else_=2,
            ),
            Task.due_date.asc(),
        )
        .all()
    )

    # Inbox: tasks with no project assigned
    inbox = (
        db.session.query(Task)
        .filter(Task.project_id.is_(None))
        .order_by(Task.created_at.desc())
        .all()
    )

    # Projects for the capture modal dropdown
    projects = db.session.query(Project).order_by(Project.name).all()

    return render_template(
        "index.html",
        on_fire=on_fire,
        delegated=delegated,
        active=active,
        backlog=backlog,
        inbox=inbox,
        projects=projects,
    )


@main_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("search.html", q="", results=[], total=0)

    task_results = []
    log_results = []
    project_results = []
    total = 0

    # Query FTS5 for tasks
    try:
        raw_conn = db.engine.raw_connection()
        cursor = raw_conn.execute(
            "SELECT task_id, rank FROM search_index WHERE search_index MATCH ? ORDER BY rank LIMIT 50",
            (q,),
        )
        rows = cursor.fetchall()
        total += len(rows)

        if rows:
            task_ids = [row[0] for row in rows]
            tasks = db.session.query(Task).filter(Task.id.in_(task_ids)).all()
            rank_map = {row[0]: row[1] for row in rows}
            for t in sorted(tasks, key=lambda x: rank_map.get(x.id, 0)):
                task_results.append(t)
        raw_conn.close()
    except Exception as e:
        app.logger.warning(f"FTS5 search failed: {e}")

    # Also search projects by name (no FTS5 for projects yet — simple ilike)
    if q:
        projects = db.session.query(Project).filter(Project.name.ilike(f"%{q}%")).order_by(Project.name).all()
        project_results = projects
        total += len(projects)

    # Search logs by title/notes (simple ilike for now)
    if q:
        logs = (
            db.session.query(Log)
            .filter(db.or_(Log.title.ilike(f"%{q}%"), Log.notes.ilike(f"%{q}%")))
            .order_by(Log.created_at.desc())
            .limit(50)
            .all()
        )
        log_results = logs
        total += len(logs)

    # Highlight function for template
    def highlight(text, term):
        if not text:
            return ""
        result = re.sub(
            rf"({re.escape(term)})",
            r'<mark class="bg-yellow-500/20 text-yellow-200 rounded px-0.5">\1</mark>',
            text,
            flags=re.IGNORECASE,
        )
        return Markup(result)

    return render_template(
        "search.html",
        q=q,
        task_results=task_results,
        log_results=log_results,
        project_results=project_results,
        total=total,
        highlight=highlight,
    )
