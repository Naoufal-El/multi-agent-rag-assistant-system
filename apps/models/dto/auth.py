from pydantic import BaseModel, EmailStr
from apps.models.dto.schemas import UserRole

# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str
    role: UserRole


class ChangePasswordRequest(BaseModel):
    """Password change request"""
    old_password: str
    new_password: str


class MessageResponse(BaseModel):
    """Generic message response"""
    success: bool
    message: str

class LoginResponse(BaseModel):
    """Login response with JWT token"""
    access_token: str
    token_type: str
    user_id: str
    email: str
    role: str