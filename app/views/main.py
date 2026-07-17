from datetime import date

import json
import re

from flask import Blueprint, current_app as app, flash, g, jsonify, redirect, request, render_template, send_file
import os
from markupsafe import Markup

from app.models import Log, Project, Task, db
from datetime import datetime

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    from datetime import timedelta
    today = date.today()
    week_end = today + timedelta(days=7 - today.weekday())  # end of current week

    # Single query for all non-done tasks (scoped to user)
    tasks = g.scoped_query(Task).filter(Task.status != "done").all()

    # Big numbers
    total_open = len(tasks)
    active_count = len([t for t in tasks if t.status == "active"])
    on_fire_count = len([t for t in tasks if t.priority == "P0" or t.status == "blocked"])
    blocked_count = len([t for t in tasks if t.status == "blocked"])
    done_count = g.scoped_query(Task).filter(Task.status == "done").count()

    # Priority counts
    priority_counts = {}
    for p in ["P0", "P1", "P2", "P3"]:
        priority_counts[p] = len([t for t in tasks if t.priority == p])
    total_priority = sum(priority_counts.values()) or 1  # avoid div by zero

    # Overdue
    overdue = sorted(
        [t for t in tasks if t.due_date and t.due_date < today],
        key=lambda t: t.due_date,
    )

    # Currently active
    currently_active = sorted(
        [t for t in tasks if t.status == "active"],
        key=lambda t: -t.created_at.timestamp(),
    )

    # Due this week
    due_this_week = sorted(
        [t for t in tasks if t.due_date and today <= t.due_date <= week_end and t.status != "done"],
        key=lambda t: t.due_date,
    )

    # Inbox
    inbox = sorted(
        [t for t in tasks if t.project_id is None],
        key=lambda t: -t.created_at.timestamp(),
    )

    # Delegated
    delegated = sorted(
        [t for t in tasks if t.status == "delegated" and t.assignee],
        key=lambda t: (t.assignee or "", -t.created_at.timestamp()),
    )

    # Recently done
    done_tasks = g.scoped_query(Task).filter(Task.status == "done").order_by(Task.completed_at.desc()).limit(5).all()

    # Project health
    projects_all = g.scoped_query(Project).order_by(Project.name).all()
    project_health = []
    for proj in projects_all:
        proj_tasks = g.scoped_query(Task).filter(Task.project_id == proj.id).all()
        done = len([t for t in proj_tasks if t.status == "done"])
        total = len(proj_tasks)
        pct = round(done / total * 100, 1) if total > 0 else 0
        next_due = None
        for t in sorted([t for t in proj_tasks if t.due_date and t.status != "done"], key=lambda x: x.due_date):
            next_due = t.due_date
            break
        project_health.append({
            "project": proj,
            "done": done,
            "total": total,
            "pct": pct,
            "next_due": next_due,
        })

    return render_template(
        "index.html",
        today=today,
        total_open=total_open,
        active_count=active_count,
        on_fire_count=on_fire_count,
        blocked_count=blocked_count,
        done_count=done_count,
        priority_counts=priority_counts,
        overdue=overdue,
        currently_active=currently_active,
        due_this_week=due_this_week,
        inbox=inbox,
        delegated=delegated,
        done_tasks=done_tasks,
        project_health=project_health,
        projects=projects_all,
    )


@main_bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("search.html", q="", task_results=[], log_results=[], project_results=[], total=0)

    task_results = []
    log_results = []
    project_results = []
    total = 0

    # Keyword search via FTS5
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
            tasks = g.scoped_query(Task).filter(Task.id.in_(task_ids)).all()
            rank_map = {row[0]: row[1] for row in rows}
            for t in sorted(tasks, key=lambda x: rank_map.get(x.id, 0)):
                task_results.append(t)
        raw_conn.close()
    except Exception as e:
        app.logger.warning(f"FTS5 search failed: {e}")

    # Also search projects by name (simple ilike)
    if q:
        projects = g.scoped_query(Project).filter(Project.name.ilike(f"%{q}%")).order_by(Project.name).all()
        project_results = projects
        total += len(projects)

    # Search logs by title/notes (simple ilike)
    if q:
        logs = (
            g.scoped_query(Log)
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
        task_scores={},  # no longer used without semantic search
    )


@main_bp.route("/board")
def board():
    project_id = request.args.get("project_id", "").strip()
    assignee = request.args.get("assignee", "").strip()

    query = g.scoped_query(Task)
    if project_id:
        query = query.filter(Task.project_id == int(project_id))
    if assignee:
        query = query.filter(Task.assignee.ilike(f"%{assignee}%"))

    tasks = query.order_by(Task.created_at.desc()).all()
    projects = g.scoped_query(Project).order_by(Project.name).all()

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
            "due_date": t.due_date.isoformat() if t.due_date else "",
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
    tasks = g.scoped_query(Task).filter(Task.due_date.isnot(None)).order_by(Task.due_date).all()
    projects = g.scoped_query(Project).order_by(Project.name).all()

    task_data = []
    for t in tasks:
        task_data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "start_date": (t.start_date or t.created_at.date()).isoformat(),
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "project_id": t.project_id,
            "recurrence": t.recurrence or None,
        })

    return render_template(
        "gantt.html",
        task_data=task_data,
        projects=projects,
        project_id=project_id,
        today_str=date.today().isoformat(),
    )


@main_bp.route("/gantt/export")
def gantt_export():
    """Generate a standalone HTML page with the Gantt chart — no app context needed."""
    from datetime import date as date_type

    project_id = request.args.get("project_id", "").strip()
    tasks = g.scoped_query(Task).filter(Task.due_date.isnot(None)).order_by(Task.due_date).all()
    projects = g.scoped_query(Project).order_by(Project.name).all()

    task_data = []
    for t in tasks:
        task_data.append({"id": t.id, "title": t.title, "status": t.status,
                          "start_date": (t.start_date or t.created_at.date()).isoformat(),
                          "due_date": t.due_date.isoformat() if t.due_date else None,
                          "project_id": t.project_id, "recurrence": t.recurrence or None})

    project_data = [{"id": p.id, "name": p.name} for p in projects]

    return render_template(
        "gantt_export.html",
        task_data=task_data,
        project_data=project_data,
        project_id=project_id,
        today_str=date_type.today().isoformat(),
    )


@main_bp.route("/gantt/report")
def gantt_report():
    """Generate a detailed markdown task report grouped by project."""
    from datetime import date as date_type, timedelta
    today = date_type.today()

    project_id = request.args.get("project_id", "").strip()
    tasks = g.scoped_query(Task).filter(Task.due_date.isnot(None)).order_by(Task.due_date).all()
    if project_id:
        tasks = [t for t in tasks if t.project_id == int(project_id)]

    # Summary counts
    total = len(tasks)
    done_count = len([t for t in tasks if t.status == "done"])
    active_count = len([t for t in tasks if t.status == "active"])
    overdue_count = len([t for t in tasks if t.due_date < today and t.status != "done"])
    blocked_count = len([t for t in tasks if t.status == "blocked"])
    p0_count = len([t for t in tasks if t.priority == "P0" and t.status != "done"])

    lines = [f"# Task Report — {today.isoformat()}", ""]

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Count |")
    lines.append(f"| --- | --- |")
    lines.append(f"| Total tasks | {total} |")
    lines.append(f"| Done | {done_count} ({round(done_count/total*100, 1) if total else 0}%) |")
    lines.append(f"| Active | {active_count} |")
    lines.append(f"| Overdue | {overdue_count} |")
    lines.append(f"| Blocked | {blocked_count} |")
    lines.append(f"| P0 (open) | {p0_count} |")
    lines.append("")

    # Group by project
    projects_map = {}
    for t in tasks:
        key = t.project.name if t.project else "Inbox"
        if key not in projects_map:
            projects_map[key] = []
        projects_map[key].append(t)

    lines.append("## By Project")
    lines.append("")

    for proj_name, proj_tasks in sorted(projects_map.items()):
        proj_done = len([t for t in proj_tasks if t.status == "done"])
        proj_total = len(proj_tasks)
        pct = round(proj_done / proj_total * 100, 1) if proj_total else 0

        lines.append(f"### {proj_name}")
        lines.append("")
        lines.append(f"**{proj_done}/{proj_total} done ({pct}%)**")
        lines.append("")

        # Overdue in this project
        proj_overdue = [t for t in proj_tasks if t.due_date < today and t.status != "done"]
        if proj_overdue:
            lines.append("#### 🔴 Overdue")
            for t in sorted(proj_overdue, key=lambda x: x.due_date):
                days = (today - t.due_date).days
                dep = f" ← blocked by **{t.blocked_by.title}**" if t.blocked_by else ""
                blocks = f" (blocks {len(t.blocks)})" if t.blocks else ""
                lines.append(f"- **{t.title}** — {t.due_date.isoformat()} ({days}d overdue) [{t.status}] {t.priority or 'P-'}{dep}{blocks}")
            lines.append("")

        # Active in this project
        proj_active = [t for t in proj_tasks if t.status == "active"]
        if proj_active:
            lines.append("#### 🟢 Active")
            for t in sorted(proj_active, key=lambda x: x.due_date or date_type(9999, 1, 1)):
                dep = f" ← blocked by **{t.blocked_by.title}**" if t.blocked_by else ""
                blocks = f" (blocks {len(t.blocks)})" if t.blocks else ""
                lines.append(f"- **{t.title}** — due {t.due_date.isoformat() if t.due_date else 'N/A'} [{t.status}] {t.priority or 'P-'}{dep}{blocks}")
            lines.append("")

        # Backlog in this project
        proj_backlog = [t for t in proj_tasks if t.status == "backlog"]
        if proj_backlog:
            lines.append("#### Backlog")
            for t in sorted(proj_backlog, key=lambda x: (x.priority or "P-", x.due_date or date_type(9999, 1, 1))):
                dep = f" ← blocked by **{t.blocked_by.title}**" if t.blocked_by else ""
                blocks = f" (blocks {len(t.blocks)})" if t.blocks else ""
                lines.append(f"- **{t.title}** — due {t.due_date.isoformat() if t.due_date else 'N/A'} [{t.status}] {t.priority or 'P-'}{dep}{blocks}")
            lines.append("")

        # Done in this project
        proj_done_tasks = [t for t in proj_tasks if t.status == "done"]
        if proj_done_tasks:
            lines.append("#### ✅ Done")
            for t in sorted(proj_done_tasks, key=lambda x: x.due_date or date_type(9999, 1, 1)):
                lines.append(f"- ~~{t.title}~~ — {t.due_date.isoformat() if t.due_date else 'N/A'}")
            lines.append("")

    # Dependency chains
    blocking_tasks = [t for t in tasks if t.blocks and t.status != "done"]
    if blocking_tasks:
        lines.append("## Dependency Chains")
        lines.append("")
        for t in sorted(blocking_tasks, key=lambda x: len(x.blocks), reverse=True):
            lines.append(f"- **{t.title}** blocks:")
            for blocked in t.blocks:
                lines.append(f"  - {blocked.title} [{blocked.status}] {blocked.priority or 'P-'}")
        lines.append("")

    return render_template(
        "gantt_report.html",
        content="\n".join(lines),
        title=f"Task Report — {today.isoformat()}",
    )


@main_bp.route("/api/calendar/events")
def calendar_events():
    tasks = g.scoped_query(Task).filter(Task.due_date.isnot(None)).all()
    events = []
    color_map = {
        "backlog": "#6b7280",
        "active": "#00e5ff",
        "delegated": "#7c4dff",
        "blocked": "#ff5252",
        "done": "#69f0ae",
    }
    for t in tasks:
        # For recurring tasks, generate occurrences within the requested range
        if t.recurrence and t.due_date:
            events.extend(_generate_recurring_events(t, color_map))
        else:
            # Show task as a span from start_date to due_date
            task_start = t.start_date or t.due_date
            events.append({
                "id": str(t.id),
                "title": t.title,
                "start": task_start.isoformat(),
                "end": t.due_date.isoformat(),
                "url": f"/tasks/{t.id}",
                "backgroundColor": color_map.get(t.status, "#6b7280"),
                "borderColor": color_map.get(t.status, "#6b7280"),
            })
    return jsonify(events)


def _generate_recurring_events(task, color_map):
    """Generate calendar events for a recurring task within the current month."""
    from datetime import timedelta
    events = []
    completed = set(task.get_completed_dates())

    # Start from due_date (first occurrence)
    start = datetime.combine(task.due_date, datetime.min.time())
    end_limit = datetime.combine(task.recurrence_end, datetime.min.time()) if task.recurrence_end else (start + timedelta(days=365))

    current = start
    while current <= end_limit:
        date_str = current.strftime("%Y-%m-%d")
        if date_str not in completed:
            events.append({
                "id": f"{task.id}:{date_str}",
                "title": task.title,
                "start": date_str,
                "url": f"/tasks/{task.id}",
                "backgroundColor": color_map.get(task.status, "#6b7280"),
                "borderColor": color_map.get(task.status, "#6b7280"),
            })

        # Advance by recurrence
        if task.recurrence == "daily":
            current += timedelta(days=1)
        elif task.recurrence == "weekly":
            current += timedelta(weeks=1)
        elif task.recurrence == "monthly":
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        else:
            break
    return events

# --- Settings ---

@main_bp.route("/settings")
def settings():
    from app.models import db
    import os
    db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    return render_template("settings.html", db_path=db_path, db_size=db_size)


@main_bp.route("/settings/export-db", methods=["POST"])
def export_db():
    from app.models import db
    import shutil
    db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    if not os.path.exists(db_path):
        flash("Database file not found", "error")
        return redirect("/settings")
    # Copy to temp file for download (avoids locking the live DB)
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    shutil.copy2(db_path, tmp.name)
    return send_file(tmp.name, as_attachment=True, download_name="taskmanager.db")


@main_bp.route("/settings/import-db", methods=["POST"])
def import_db():
    from app.models import db
    import shutil
    db_path = app.config.get("SQLALCHEMY_DATABASE_URI", "").replace("sqlite:///", "")
    if "db_file" not in request.files:
        flash("No file uploaded", "error")
        return redirect("/settings")
    f = request.files["db_file"]
    if not f.filename or not f.filename.endswith(".db"):
        flash("Invalid file — must be a .db file", "error")
        return redirect("/settings")
    # Safety backup
    backup_path = db_path + ".backup"
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
    try:
        f.save(db_path)
        flash("Database imported successfully", "success")
    except Exception as e:
        # Rollback from safety backup
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
            os.remove(backup_path)
        flash(f"Import failed: {e}", "error")
    return redirect("/settings")

# --- User Management ---

@main_bp.route("/settings/users", methods=["GET", "POST"])
def settings_users():
    from flask_login import current_user
    from app.models import User

    if not current_user.is_admin:
        flash("Only administrators can manage users", "error")
        return redirect(url_for("main.settings"))

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            is_admin = request.form.get("is_admin") == "on"

            if not username:
                flash("Username is required", "error")
            elif not password:
                flash("Password is required", "error")
            elif User.query.filter_by(username=username).first():
                flash(f"User \"{username}\" already exists", "error")
            else:
                user = User(username=username, is_admin=is_admin)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f"User \"{username}\" created", "success")

        elif action == "reset_password":
            user_id = int(request.form.get("user_id", 0))
            new_password = request.form.get("new_password", "")
            if not new_password:
                flash("Password cannot be empty", "error")
            else:
                target = db.session.get(User, user_id)
                if target:
                    target.set_password(new_password)
                    db.session.commit()
                    flash(f"Password reset for \"{target.username}\"", "success")

        elif action == "change_own_password":
            new_password = request.form.get("new_password", "")
            if not new_password:
                flash("Password cannot be empty", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Your password has been changed", "success")

        return redirect(url_for("main.settings_users"))

    users = User.query.order_by(User.is_admin.desc(), User.username).all()
    return render_template("settings/users.html", users=users)
