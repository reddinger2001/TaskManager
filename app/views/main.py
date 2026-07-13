import json
import re

from flask import Blueprint, current_app as app, jsonify, request, render_template
from markupsafe import Markup

from app.models import Log, Project, Task, db
from datetime import datetime

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
        .filter(Task.status == "delegated", Task.assignee.isnot(None))
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
        return render_template("search.html", q="", task_results=[], log_results=[], project_results=[], total=0)

    use_semantic = request.args.get("semantic", "true").lower() == "true"

    task_results = []
    task_scores = {}  # task_id -> combined_score for display
    log_results = []
    project_results = []
    total = 0

    if use_semantic:
        # Hybrid search: combine FTS5 keyword + sqlite-vec semantic
        try:
            from app.services.embedding import hybrid_search
            results = hybrid_search(q, limit=50, semantic_weight=0.6)
            if results:
                task_ids = [row[0] for row in results]
                tasks = db.session.query(Task).filter(Task.id.in_(task_ids)).all()
                score_map = {row[0]: row[1] for row in results}
                for t in sorted(tasks, key=lambda x: score_map.get(x.id, 0), reverse=True):
                    task_results.append(t)
                    task_scores[t.id] = score_map.get(t.id, 0)
                total += len(task_results)
        except Exception as e:
            app.logger.warning(f"Hybrid search failed: {e}")
    else:
        # Keyword-only search via FTS5
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

    # Also search projects by name (simple ilike)
    if q:
        projects = db.session.query(Project).filter(Project.name.ilike(f"%{q}%")).order_by(Project.name).all()
        project_results = projects
        total += len(projects)

    # Search logs by title/notes (simple ilike)
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
        use_semantic=use_semantic,
        task_scores=task_scores,
    )


@main_bp.route("/board")
def board():
    project_id = request.args.get("project_id", "").strip()
    assignee = request.args.get("assignee", "").strip()

    query = db.session.query(Task)
    if project_id:
        query = query.filter(Task.project_id == int(project_id))
    if assignee:
        query = query.filter(Task.assignee.ilike(f"%{assignee}%"))

    tasks = query.order_by(Task.created_at.desc()).all()
    projects = Project.query.order_by(Project.name).all()

    # Collect unique assignees
    assignees = sorted(set(t.assignee for t in tasks if t.assignee))

    # Serialize tasks for Alpine.js
    task_data = []
    for t in tasks:
        tags = t.get_tags() if t.tags else []
        task_data.append({
            "id": t.id,
            "title": t.title,
            "description": (t.description or "")[:200],
            "status": t.status,
            "priority": t.priority or "",
            "assignee": t.assignee or "",
            "project": t.project.name if t.project else "",
            "project_id": t.project_id,
            "due_date": t.due_date if t.due_date else "",
            "tags": tags,
        })

    return render_template(
        "board.html",
        task_data=task_data,
        projects=projects,
        assignees=assignees,
        project_id=project_id,
        assignee=assignee,
    )


@main_bp.route("/calendar")
def calendar():
    return render_template("calendar.html")


@main_bp.route("/gantt")
def gantt():
    project_id = request.args.get("project_id", "").strip()
    tasks = Task.query.filter(Task.due_date.isnot(None)).order_by(Task.due_date).all()
    projects = Project.query.order_by(Project.name).all()

    task_data = []
    for t in tasks:
        task_data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date,
            "project_id": t.project_id,
        })

    return render_template(
        "gantt.html",
        task_data=task_data,
        projects=projects,
        project_id=project_id,
    )


@main_bp.route("/api/calendar/events")
def calendar_events():
    tasks = Task.query.filter(Task.due_date.isnot(None)).all()
    events = []
    for t in tasks:
        color_map = {
            "backlog": "#6b7280",
            "active": "#00e5ff",
            "delegated": "#7c4dff",
            "blocked": "#ff5252",
            "done": "#69f0ae",
        }
        events.append({
            "id": str(t.id),
            "title": t.title,
            "start": t.due_date,
            "url": f"/tasks/{t.id}",
            "backgroundColor": color_map.get(t.status, "#6b7280"),
            "borderColor": color_map.get(t.status, "#6b7280"),
        })
    return jsonify(events)
