"""
services/task_service.py
------------------------
Business logic for Task CRUD.
All DB operations go through this layer so routers stay thin.
"""

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskUpdate


class TaskNotFound(Exception):
    pass


class TaskForbidden(Exception):
    pass


class TaskService:

    def create_task(self, db: Session, payload: TaskCreate, owner: User) -> Task:
        """Create a new task owned by the current user."""
        task = Task(
            title=payload.title,
            description=payload.description,
            status=payload.status,
            due_date=payload.due_date,
            owner_id=owner.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def get_user_tasks(
        self,
        db: Session,
        owner: User,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
    ) -> TaskListResponse:
        """
        Return paginated tasks belonging to the current user.
        Admins see all tasks if they wish; regular users only see their own.
        """
        query = db.query(Task).filter(Task.owner_id == owner.id)

        if status_filter:
            query = query.filter(Task.status == status_filter)

        total = query.count()
        items = (
            query
            .order_by(Task.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return TaskListResponse(items=items, total=total, page=page, page_size=page_size)

    def get_task_by_id(self, db: Session, task_id: int, owner: User) -> Task:
        """
        Fetch a single task.
        Raises TaskNotFound if it doesn't exist.
        Raises TaskForbidden if it belongs to a different user (unless admin).
        """
        from app.models.user import UserRole

        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise TaskNotFound(f"Task {task_id} not found")

        # Admins can view any task; regular users only their own
        if owner.role != UserRole.ADMIN and task.owner_id != owner.id:
            raise TaskForbidden("You do not have access to this task")

        return task

    def update_task(
        self, db: Session, task_id: int, payload: TaskUpdate, owner: User
    ) -> Task:
        """
        Partial update — only fields present in the payload are changed.
        model_dump(exclude_unset=True) is the Pydantic v2 way to do this.
        """
        task = self.get_task_by_id(db, task_id, owner)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)

        db.commit()
        db.refresh(task)
        return task

    def delete_task(self, db: Session, task_id: int, owner: User) -> None:
        """Delete a task. Regular users can only delete their own tasks."""
        task = self.get_task_by_id(db, task_id, owner)
        db.delete(task)
        db.commit()
