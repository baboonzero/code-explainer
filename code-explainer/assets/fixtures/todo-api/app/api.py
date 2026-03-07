from fastapi import APIRouter
from pydantic import BaseModel

from app.services.tasks import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
service = TaskService()


class TaskCreate(BaseModel):
    title: str


@router.get("")
def list_tasks() -> list[dict]:
    return service.list_tasks()


@router.post("")
def create_task(payload: TaskCreate) -> dict:
    return service.create_task(payload.title)
