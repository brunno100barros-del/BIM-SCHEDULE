from fastapi import APIRouter
from app.api.v1.endpoints import projects, ifc

api_router = APIRouter()
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(ifc.router, prefix="/ifc", tags=["ifc"])
