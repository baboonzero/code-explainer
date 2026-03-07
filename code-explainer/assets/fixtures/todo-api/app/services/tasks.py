from app.repositories.task_store import TaskStore


class TaskService:
    def __init__(self) -> None:
        self.store = TaskStore()

    def list_tasks(self) -> list[dict]:
        return self.store.list_all()

    def create_task(self, title: str) -> dict:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("title is required")
        return self.store.create(cleaned)
