"""V1 API Router"""
from fastapi import APIRouter
from app.api.v1.detect import router as detect_router
from app.api.v1.tasks import router as tasks_router

api_router = APIRouter()
api_router.include_router(detect_router, prefix="/detect", tags=["detection"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
from app.api.v1.upload import router as upload_router
api_router.include_router(upload_router, prefix="/upload", tags=["upload"])
