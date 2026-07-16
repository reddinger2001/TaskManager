import json
from datetime import date, datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

db = SQLAlchemy()


class Project(db.Model):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id"), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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


class Log(db.Model):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)

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
