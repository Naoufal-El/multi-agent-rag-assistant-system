# apps/controllers/authController.py

"""
Authentication Controller - HTTP Endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends

from apps.models.dto.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ChangePasswordRequest,
    MessageResponse
)
from apps.services.authService import auth_service
from apps.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login endpoint - Returns JWT token
    """
    result = await auth_service.authenticate_user(
        email=request.email,
        password=request.password
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["error"],
            headers={"WWW-Authenticate": "Bearer"},
        )


    user_dict = result["user"]

    return LoginResponse(
        access_token=result["token"],
        token_type="bearer",
        user_id=user_dict["id"],
        email=user_dict["email"],
        role=user_dict["role"]
    )


@router.post("/register", response_model=LoginResponse)
async def register(request: RegisterRequest):
    """
    Registration endpoint - Creates new user
    """
    result = await auth_service.register_user(
        email=request.email,
        password=request.password,
        role=request.role
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    user_data = result["user"]

    if hasattr(user_data, 'id'):
        user_dict = {
            "id": str(user_data.id),
            "email": user_data.email,
            "role": user_data.role.value
        }
    else:
        user_dict = user_data

    return LoginResponse(
        access_token=result["token"],
        token_type="bearer",
        user_id=user_dict["id"],
        email=user_dict["email"],
        role=user_dict["role"]
    )

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
        request: ChangePasswordRequest,
        current_user: dict = Depends(get_current_user)
):
    """
    Change password - Requires authentication
    """
    result = await auth_service.change_password(
        email=current_user["email"],
        old_password=request.old_password,
        new_password=request.new_password
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )

    return MessageResponse(
        success=True,
        message="Password updated successfully"
    )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current user info from JWT token
    """
    return {
        "user_id": current_user["id"],
        "email": current_user["email"],
        "role": current_user["role"]
    }
