from fastapi import FastAPI

from app.api import router

app = FastAPI(title="Todo API")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
