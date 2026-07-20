import json
from datetime import date, datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", backref="owner", lazy="select")
    projects: Mapped[list["Project"]] = relationship("Project", backref="owner", lazy="select")
    logs: Mapped[list["Log"]] = relationship("Log", backref="owner", lazy="select")

    def set_password(self, password: str):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def __repr__(self):        return f"<User {self.username}>"


def scoped_get(model, model_id, user):
    """Get a single object by ID, respecting the current user's scope.

    Returns the object if visible to the user, or None if not in scope.
    Use this instead of scoped_query(Model).get_or_404(id) which breaks
    when the scoped query has filter criteria (SQLAlchemy doesn't allow
    .get() on filtered queries).
    """
    from flask import abort
    obj = db.session.get(model, model_id)
    if obj is None:
        abort(404)
    # Admin sees everything
    if user.is_admin:
        return obj
    # Check scope: is this object visible to the user?
    query = scoped_query(model, user)
    if model.query.filter(model.id == model_id).first() is not None:
        # Object exists — check if it's in scope by testing the scoped filter
        pass
    # Simpler approach: just test if the object appears in a scoped list
    if model == Task:
        if obj.user_id == user.id or obj.assignee and obj.assignee.lower() == user.username.lower():
            return obj
        if obj.project_id:
            proj = db.session.get(Project, obj.project_id)
            if proj and _user_can_see_project(proj, user):
                return obj
    elif model == Project:
        if _user_can_see_project(obj, user):
            return obj
    elif model == Log:
        if obj.user_id == user.id:
            return obj
        if obj.project_id:
            proj = db.session.get(Project, obj.project_id)
            if proj and _user_can_see_project(proj, user):
                return obj
    abort(404)


def _user_can_see_project(project, user):
    """Check if a non-admin user can see a project."""
    if project.user_id == user.id:
        return True
    shared = project.get_shared_user_ids()
    if user.id in shared:
        return True
    return False


def scoped_query(model, user):
    """Return a query filtered by the current user's scope.

    Admin users see everything. Regular users see:
    - Items they own (user_id == their id)
    - Projects shared with them (their id in project.shared_with)
    - Tasks belonging to shared projects
    """
    if user.is_admin:
        return model.query

    if model == Project:
        from sqlalchemy import or_
        return Project.query.filter(
            or_(
                Project.user_id == user.id,
                # Check if user id is in the shared_with JSON array
                Project.shared_with.isnot(None),
                Project.shared_with.contains(str(user.id)),
            )
        )

    if model == Task:
        from sqlalchemy import or_
        # User's own tasks + tasks in shared projects + tasks assigned to them
        shared_project_ids = db.session.query(Project.id).filter(
            Project.user_id != user.id,
            Project.shared_with.isnot(None),
            Project.shared_with.contains(str(user.id)),
        ).subquery()
        return Task.query.filter(
            or_(
                Task.user_id == user.id,
                Task.project_id.in_(db.session.query(shared_project_ids.c.id)),
                Task.assignee.ilike(f"%{user.username}%"),
            )
        )

    if model == Log:
        from sqlalchemy import or_
        # User's own logs + logs on their tasks + logs on shared projects
        shared_project_ids = db.session.query(Project.id).filter(
            Project.user_id != user.id,
            Project.shared_with.isnot(None),
            Project.shared_with.contains(str(user.id)),
        ).subquery()
        return Log.query.filter(
            or_(
                Log.user_id == user.id,
                Log.project_id.in_(db.session.query(shared_project_ids.c.id)),
            )
        )

    # Fallback: just return unfiltered (shouldn't happen)
    return model.query


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    shared_with: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of user_ids

    def get_shared_user_ids(self):
        if not self.shared_with:
            return []
        try:
            return json.loads(self.shared_with)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_shared_with(self, value):
        self.shared_with = json.dumps(value) if value else None

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    children: Mapped[list["Project"]] = relationship(
        "Project", backref=backref("parent", remote_side="Project.id"), lazy="select"
    )

    def get_descendant_ids(self, include_self=True):
        """Get IDs of this project and all descendants using a recursive CTE.

        Single SQL query instead of N+1 Python traversal.
        """
        from sqlalchemy import text

        result = db.session.execute(
            text("""
                WITH RECURSIVE descendants(id) AS (
                    SELECT :root_id
                    UNION ALL
                    SELECT p.id FROM projects p INNER JOIN descendants d ON p.parent_id = d.id
                )
                SELECT id FROM descendants
            """),
            {"root_id": self.id},
        ).fetchall()

        ids = {row[0] for row in result}
        if not include_self:
            ids.discard(self.id)
        return ids

    def is_ancestor_of(self, other_project):
        """Check if this project is an ancestor of another (prevents circular refs)."""
        return other_project.id in self.get_descendant_ids()
    tasks: Mapped[list["Task"]] = relationship("Task", backref="project", lazy="select")
    logs: Mapped[list["Log"]] = relationship("Log", backref="project", lazy="select", cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self):
        return f"<Project {self.name}>"


class Task(db.Model):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="backlog")
    priority: Mapped[str | None] = mapped_column(String(5), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recurrence: Mapped[str | None] = mapped_column(String(10), nullable=True)   # daily, weekly, monthly
    recurrence_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_dates: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON array of YYYY-MM-DD
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    depends_on_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )

    # JSON fields stored as text
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of strings
    links: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of {url, label}

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    logs: Mapped[list["Log"]] = relationship("Log", backref="task", lazy="select", cascade="all, delete-orphan", passive_deletes=True)
    blocked_by: Mapped["Task | None"] = relationship(
        "Task", remote_side="Task.id", backref=backref("blocks", lazy="select"), lazy="select"
    )

    def get_tags(self):
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, value):
        self.tags = json.dumps(value) if value else None

    def get_links(self):
        if not self.links:
            return []
        try:
            return json.loads(self.links)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_links(self, value):
        self.links = json.dumps(value) if value else None

    def get_completed_dates(self):
        if not self.completed_dates:
            return []
        try:
            return json.loads(self.completed_dates)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_completed_dates(self, value):
        self.completed_dates = json.dumps(value) if value else None

    def would_create_cycle(self, other_task_id: int) -> bool:
        """Check if setting depends_on_id=other_task_id would create a circular dependency.

        Walks the chain upward from other_task_id to see if we'd loop back to self.
        """
        visited = set()
        current_id = other_task_id
        while current_id is not None:
            if current_id == self.id:
                return True  # cycle detected
            if current_id in visited:
                break  # unrelated cycle elsewhere, not involving us
            visited.add(current_id)
            parent = db.session.get(Task, current_id)
            current_id = parent.depends_on_id if parent else None
        return False

    def __repr__(self):
        return f"<Task {self.title}>"


class AppSettings(db.Model):
    """Single-row settings table for app-wide configuration."""
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    priorities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of priority strings

    def get_priorities(self):
        if not self.priorities:
            return ["P0", "P1", "P2"]
        try:
            return json.loads(self.priorities)
        except (json.JSONDecodeError, TypeError):
            return ["P0", "P1", "P2"]

    def set_priorities(self, value):
        self.priorities = json.dumps(value) if value else None

    @staticmethod
    def get():
        """Return the single settings row, creating it if needed."""
        settings = AppSettings.query.first()
        if not settings:
            settings = AppSettings()
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f"<AppSettings priorities={self.get_priorities()}>"


class Log(db.Model):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "(task_id IS NOT NULL) OR (project_id IS NOT NULL)",
            name="ck_log_must_have_parent",
        ),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<Log {self.title}>"
