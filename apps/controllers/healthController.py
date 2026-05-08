from fastapi import APIRouter
from apps.models.dto.schemas import HealthDTO
from apps.services.HealthService import healthService
from apps.middleware.auth_middleware import require_employee_admin
from fastapi import Depends

router = APIRouter()

@router.get("/health", response_model=HealthDTO, dependencies=[Depends(require_employee_admin)])
async def health():
    """Health check endpoint with dependency status"""
    result = await healthService.health_check()
    return HealthDTO(status="OK", result=result)