class TaskStore:
    def __init__(self) -> None:
        self._tasks: list[dict] = []

    def list_all(self) -> list[dict]:
        return list(self._tasks)

    def create(self, title: str) -> dict:
        task = {"id": len(self._tasks) + 1, "title": title, "done": False}
        self._tasks.append(task)
        return task
