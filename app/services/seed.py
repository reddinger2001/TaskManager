"""Database seeder — creates tutorial data on first run."""

from __future__ import annotations

import logging

from datetime import date, timedelta

logger = logging.getLogger(__name__)


def seed_if_empty(app):
    """Populate the database with tutorial tasks if it is empty.

    Only runs when there are zero projects and zero tasks — i.e. a fresh install.
    Creates 3 sample projects and ~12 tasks demonstrating the workflow:
    inbox capture → triage → active work → dependencies → done.
    """
    from app.models import Project, Task, User, db

    with app.app_context():
        if User.query.count() > 0:
            return  # Database already has data

        today = date.today()

        logger.info("Seeding database with tutorial data...")

        # --- Admin user ---
        admin = User(username="admin", is_admin=True)
        admin.set_password("admin")
        db.session.add(admin)
        db.session.flush()

        logger.info("Created admin user (username: admin, password: admin)")

        # --- Projects ---
        proj_personal = Project(
            name="Personal — Getting Started",
            description="Tutorial project showing how to use TaskManager",
            color="#00e5ff",
            user_id=admin.id,
        )
        proj_work = Project(
            name="Work — Q3 Planning",
            description="Example project with dependencies and priorities",
            color="#7c4dff",
            user_id=admin.id,
        )
        proj_someday = Project(
            name="Someday / Maybe",
            description="Low-priority ideas you can revisit later",
            color="#6b7280",
            user_id=admin.id,
        )

        db.session.add_all([proj_personal, proj_work, proj_someday])
        db.session.flush()

        # --- Tasks ---
        tasks = [
            # Inbox: untriaged items (no project)
            Task(
                title="📥 Welcome to TaskManager!",
                description=(
                    "This is your inbox — the fastest way to capture a task.\n\n"
                    "**How it works:**\n"
                    "1. Hit Ctrl+K (or /) to open the quick-capture modal\n"
                    "2. Type a title and hit Enter\n"
                    "3. Come back later to triage: assign a project, set priority, pick a status\n\n"
                    "This task is in your **Inbox** — it has no project assigned yet. "
                    "Click it to open the detail view where you can organize it."
                ),
                user_id=admin.id,
                status="inbox",
            ),
            Task(
                title="📥 Another inbox item — quick capture demo",
                description=(
                    "This is another untriaged task in your inbox. "
                    "Inbox items have no project, no priority, and no due date.\n\n"
                    "**Tip:** Try assigning this to the 'Personal — Getting Started' project below."
                ),
                user_id=admin.id,
                status="inbox",
            ),
            # Active: what you're working on right now
            Task(
                title="✅ Mark this task as done",
                description=(
                    "This task is **active** — meaning it's something you're currently working on.\n\n"
                    "**Try it:** Change the status to 'Done' and watch it disappear from your dashboard. "
                    "It will appear in the 'Recently Done' section instead."
                ),
                user_id=admin.id,
                status="active",
                priority="P3",
                project_id=proj_personal.id,
                due_date=today + timedelta(days=7),
            ),
            Task(
                title="🔗 Explore task dependencies",
                description=(
                    "This task is **blocked by** the task below it. Try opening that task to see how dependencies work.\n\n"
                    "**Dependencies:** A task can depend on another. When the blocker is done, you'll see a green '(resolved)' badge."
                ),
                user_id=admin.id,
                status="active",
                priority="P2",
                project_id=proj_work.id,
                due_date=today + timedelta(days=14),
            ),
            Task(
                title="🔗 Complete me first — I block the task above",
                description=(
                    "This is a **blocking task**. The task 'Explore task dependencies' depends on this one.\n\n"
                    "When you mark this as done, the dependent task will show '(resolved)' next to its blocked-by badge."
                ),
                user_id=admin.id,
                status="active",
                priority="P2",
                project_id=proj_work.id,
                due_date=today + timedelta(days=3),
            ),
            # On Fire: P0 / urgent
            Task(
                title="🔥 Fix the production database backup issue",
                description=(
                    "This is a **P0 (On Fire)** task — the highest priority.\n\n"
                    "P0 tasks appear at the top of your dashboard in the 'On Fire' section. "
                    "Use P0 sparingly — if everything is P0, nothing is."
                ),
                user_id=admin.id,
                status="active",
                priority="P0",
                project_id=proj_work.id,
                due_date=today + timedelta(days=1),
            ),
            # Backlog: planned but not started
            Task(
                title="📋 Write API documentation for new endpoints",
                description=(
                    "This task is in the **backlog** — it's planned but not yet active.\n\n"
                    "When you're ready to work on it, change the status to 'Active'."
                ),
                user_id=admin.id,
                status="backlog",
                priority="P1",
                project_id=proj_work.id,
                due_date=today + timedelta(days=21),
            ),
            Task(
                title="📋 Set up automated testing pipeline",
                description=(
                    "Another backlog item with a **due date**. Tasks in the backlog are sorted by priority then due date.\n\n"
                    "**Priority levels:**\n"
                    "- P0: On Fire — do it now\n"
                    "- P1: High — important, schedule soon\n"
                    "- P2: Medium — normal work\n"
                    "- P3: Low — nice to have"
                ),
                user_id=admin.id,
                status="backlog",
                priority="P2",
                project_id=proj_work.id,
                due_date=today + timedelta(days=30),
            ),
            Task(
                title="📋 Review and update security policies",
                user_id=admin.id,
                description="A medium-priority backlog item.",
                status="backlog",
                priority="P2",
                project_id=proj_work.id,
                due_date=today + timedelta(days=45),
            ),
            # Delegated
            Task(
                title="👤 Review PR #42 — assigned to Sarah",
                description=(
                    "This task is **delegated** to Sarah. Delegated tasks appear in their own section on the dashboard.\n\n"
                    "Use this for tasks you've assigned to someone else but still need to track."
                ),
                user_id=admin.id,
                status="delegated",
                assignee="Sarah",
                project_id=proj_work.id,
            ),
            # Someday / Maybe
            Task(
                title="💡 Explore AI-powered task categorization",
                description=(
                    "This is in the **Someday / Maybe** project — ideas you want to revisit later.\n\n"
                    "Projects are just a way to group related tasks. Create as many as you need."
                ),
                user_id=admin.id,
                status="backlog",
                priority="P3",
                project_id=proj_someday.id,
            ),
            Task(
                title="💡 Learn more about SQLite full-text search",
                user_id=admin.id,
                description="Another someday idea.",
                status="backlog",
                priority="P3",
                project_id=proj_someday.id,
            ),
        ]

        db.session.add_all(tasks)
        db.session.flush()

        # Set up dependency: "Explore task dependencies" (index 3) depends on "Complete me first" (index 4)
        tasks[3].depends_on_id = tasks[4].id

        db.session.commit()

        logger.info("Seeded %d projects and %d tasks", Project.query.count(), Task.query.count())
