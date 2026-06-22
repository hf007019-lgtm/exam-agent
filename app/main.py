from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.imports import router as imports_router
from app.api.v1.reports import router as reports_router
from app.api.v1.runs import router as runs_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.user import router as user_router
from app.core.config import settings
from app.db.database import database_path, initialize_database


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
)


app.include_router(agent_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(runs_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/")
def index() -> FileResponse:
    """返回招考政策智能分析 Agent 工作台页面。"""
    response = FileResponse("app/static/index.html")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/v1/health")
def health_check() -> dict:
    """提供健康检查接口，方便确认服务是否正常启动。"""
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "database": {
            "status": "ready",
            "engine": "sqlite",
            "file": database_path().name,
        },
        "auth_enabled": settings.AUTH_ENABLED,
    }
