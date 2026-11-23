from fastapi import APIRouter

from app.jobs.router import router as jobs_router
from app.modules.ai.router import router as ai_router
from app.modules.ifc.router import router as ifc_router
from app.modules.planning.router import router as planning_router
from app.modules.projects.router import router as projects_router
from app.modules.system.router import router as system_router
from app.modules.takeoff.router import generator_router, takeoff_router

api_router = APIRouter()
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(ifc_router, prefix="/ifc", tags=["ifc"])
# O prefixo /activities é mantido por compatibilidade com o frontend e os testes existentes.
api_router.include_router(planning_router, prefix="/activities", tags=["planning"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_router.include_router(takeoff_router, prefix="/takeoff", tags=["takeoff"])
api_router.include_router(generator_router, prefix="/schedule-generator", tags=["schedule-generator"])
