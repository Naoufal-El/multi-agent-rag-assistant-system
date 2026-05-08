# apps/services/authService.py

"""
Authentication Service - Business Logic for User Authentication

Handles:
- User login with JWT token generation
- User registration
- Token validation
- Password management
"""

from typing import Optional, Dict
from datetime import datetime, timedelta, UTC
import jwt
from apps.config import settings
from apps.repository.user_manager import user_manager
from apps.models.dto.schemas import UserRole



class AuthService:
    """
    Authentication business logic

    Responsibilities:
    - JWT token generation
    - User authentication orchestration
    - Password validation
    - Token verification
    """

    def __init__(self):
        print("[AuthService] Initialized")

    # =====================================================
    # TOKEN GENERATION
    # =====================================================

    def create_access_token(
            self,
            user_id: str,
            email: str,
            role: str,
            expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Generate JWT access token

        Args:
            user_id: User UUID (as string)
            email: User email
            role: User role (admin/employee/customer)
            expires_delta: Custom expiration time (optional)

        Returns:
            JWT token string
        """
        # Build payload
        payload = {
            "sub": user_id,      # Subject (user ID)
            "email": email,
            "role": role,
            "iat": datetime.now(UTC),  # Issued at
        }

        # Set expiration
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(minutes=settings.auth.min_to_expire)

        payload["exp"] = expire

        # Encode token
        token = jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)

        print(f"[AuthService] Token created for {email} (expires in {settings.auth.min_to_expire} min)")
        return token

    # =====================================================
    # AUTHENTICATION
    # =====================================================

    async def authenticate_user(
            self,
            email: str,
            password: str,
    ) -> Dict[str, any]:
        """
        Authenticate user and generate access token

        Args:
            email: User email
            password: Plain text password
            role: User role enum

        Returns:
            dict: {
                "success": bool,
                "token": str (if success),
                "user": User object (if success),
                "error": str (if failure)
            }
        """
        try:
            # ✅ authenticate_user returns Dict or None
            user_dict = await user_manager.authenticate_user(email, password)

            if not user_dict:
                return {
                    "success": False,
                    "error": "Invalid email or password"
                }

            # user_dict is already a dict with id, email, role, username
            # No need to check is_active - it's already checked in user_manager

            # Generate JWT token
            token = self.create_access_token(
                user_id=user_dict["id"],
                email=user_dict["email"],
                role=user_dict["role"]
            )

            print(f"[AuthService] Login successful: {email}")

            return {
                "success": True,
                "token": token,
                "user": user_dict
            }

        except Exception as e:
            print(f"[AuthService] Login error: {e}")
            return {
                "success": False,
                "error": f"Login failed: {str(e)}"
            }

    # =====================================================
    # USER REGISTRATION
    # =====================================================

    async def register_user(
            self,
            email: str,
            password: str,
            role: UserRole
    ) -> Dict[str, any]:
        """
        Register new user

        Args:
            email: User email
            password: Plain text password
            role: User role enum

        Returns:
            dict: {
                "success": bool,
                "token": str (if success),
                "user": User object (if success),
                "error": str (if failure)
            }
        """
        try:
            # Check if user already exists
            existing_user = await user_manager.get_user_by_email(email)

            if existing_user:
                return {
                    "success": False,
                    "error": "Email already registered"
                }

            # Create new user
            user = await user_manager.create_user(email, password, role)

            # Generate JWT token
            token = self.create_access_token(
                user_id=str(user.id),
                email=user.email,
                role=user.role.value
            )

            print(f"[AuthService] User registered: {user.email}")

            return {
                "success": True,
                "token": token,
                "user": user
            }

        except Exception as e:
            print(f"[AuthService] Registration error: {e}")
            return {
                "success": False,
                "error": f"Registration failed: {str(e)}"
            }

    # =====================================================
    # PASSWORD MANAGEMENT
    # =====================================================

    async def change_password(
            self,
            email: str,
            old_password: str,
            new_password: str
    ) -> Dict[str, any]:
        """
        Change user password

        Args:
            email: User email
            old_password: Current password (for verification)
            new_password: New password

        Returns:
            dict: {"success": bool, "error": str (if failure)}
        """
        try:
            # Verify old password
            user = await user_manager.get_user_by_email(email)

            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }

            # Verify old password
            if not user_manager.verify_password(old_password, user.hashed_password):
                return {
                    "success": False,
                    "error": "Current password is incorrect"
                }

            # Update password
            success = await user_manager.update_password(email, new_password)

            if success:
                print(f"[AuthService] Password changed for {email}")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error": "Failed to update password"
                }

        except Exception as e:
            print(f"[AuthService] Password change error: {e}")
            return {
                "success": False,
                "error": f"Password change failed: {str(e)}"
            }

    # =====================================================
    # TOKEN VALIDATION
    # =====================================================

    def verify_token(self, token: str) -> Dict[str, any]:
        """
        Verify JWT token (used by middleware)

        Args:
            token: JWT token string

        Returns:
            dict: {
                "valid": bool,
                "payload": dict (if valid),
                "error": str (if invalid)
            }
        """
        try:
            payload = jwt.decode(token, settings.auth.secret_key, algorithms=[settings.auth.algorithm])

            return {
                "valid": True,
                "payload": payload
            }

        except jwt.ExpiredSignatureError:
            return {
                "valid": False,
                "error": "Token has expired"
            }

        except jwt.InvalidTokenError:
            return {
                "valid": False,
                "error": "Invalid token"
            }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Token verification failed: {str(e)}"
            }


# Singleton instance
auth_service = AuthService()