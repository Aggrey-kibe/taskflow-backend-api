"""
routers/tasks.py
----------------
Task CRUD endpoints — all require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.task import TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task_service import TaskForbidden, TaskNotFound, TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])
_service = TaskService()


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _service.create_task(db, payload, current_user)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all tasks belonging to the current user (paginated)",
)
def list_tasks(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _service.get_user_tasks(db, current_user, page, page_size, status_filter)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a single task by ID",
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _service.get_task_by_id(db, task_id, current_user)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TaskForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Partially update a task",
)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _service.update_task(db, task_id, payload, current_user)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TaskForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _service.delete_task(db, task_id, current_user)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except TaskForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
