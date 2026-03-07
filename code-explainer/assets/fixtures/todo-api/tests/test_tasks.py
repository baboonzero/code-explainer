from app.services.tasks import TaskService


def test_create_task() -> None:
    service = TaskService()
    task = service.create_task("Ship onboarding")
    assert task["title"] == "Ship onboarding"
