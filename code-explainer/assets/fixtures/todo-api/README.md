# Todo API

Todo API is a small FastAPI service for creating, listing, and completing team tasks.
It is designed to be easy to onboard onto: HTTP routes live in `app/api.py`, business rules live in `app/services/`, and persistence lives in `app/repositories/`.

## Architecture

- `app/main.py` boots the FastAPI application.
- `app/api.py` exposes task endpoints.
- `app/services/tasks.py` owns validation and task workflows.
- `app/repositories/task_store.py` stores tasks in memory for now.
- `tests/` verifies the task lifecycle.

## Main flow

1. A client calls the tasks API.
2. The API delegates to the task service.
3. The task service validates and transforms data.
4. The repository persists or reads tasks.
5. The API returns the result.
