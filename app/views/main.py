from flask import Blueprint, render_template

from app.models import Project, Task, db

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
