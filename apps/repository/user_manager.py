# apps/repository/user_manager.py

"""
User Manager - Authentication & User Management

Uses Argon2id for password hashing (OWASP recommended)
Integrates with PostgreSQL for persistent user storage
Auto-creates users on first authentication attempt
"""

from typing import Optional, Dict
from sqlalchemy import select
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from apps.models.entity.user import User
from apps.models.dto.schemas import UserRole
from apps.repository.postgres_manager import postgres_manager

# Argon2 password hasher (winner of Password Hashing Competition)
ph = PasswordHasher()


class UserManager:
    """
    User management with basic authentication

    Features:
    - Argon2id password hashing (OWASP recommended)
    - No password length limits
    - Automatic rehashing if parameters change
    - Auto-creates users on first authentication
    - PostgreSQL integration for persistence
    """

    def __init__(self):
        print("[UserManager] Initialized (Argon2id password hashing)")

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using Argon2id

        Args:
            password: Plain text password (any length)

        Returns:
            Argon2 hash string
        """
        return ph.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its Argon2 hash

        Args:
            plain_password: Plain text password to verify
            hashed_password: Stored Argon2 hash

        Returns:
            True if password matches, False otherwise
        """
        try:
            ph.verify(hashed_password, plain_password)

            # Check if hash needs rehashing (parameters changed)
            if ph.check_needs_rehash(hashed_password):
                print("[UserManager] ⚠️  Password hash needs updating (parameters changed)")

            return True

        except VerifyMismatchError:
            return False

        except Exception as e:
            print(f"[UserManager] ❌ Password verification error: {e}")
            return False

    async def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """
        Authenticate a user by email and password

        Args:
            email: User's email
            password: Plain text password

        Returns:
            User dict if authenticated, None otherwise
        """
        async with postgres_manager.get_session() as session:
            # Find user by email
            user = await session.scalar(
                select(User).where(User.email == email)
            )

            if not user:
                print(f"[UserManager] ❌ User not found: {email}")
                return None

            # Check if account is active
            if not user.is_active:
                print(f"[UserManager] ❌ Account deactivated: {email}")
                return None

            # Verify password
            if not self.verify_password(password, user.hashed_password):
                print(f"[UserManager] ❌ Invalid password for: {email}")
                return None

            print(f"[UserManager] ✅ Authenticated: {email} (role={user.role.value})")

            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "role": user.role.value
            }

    async def create_user(
            self,
            email: str,
            password: str,
            role: UserRole
    ) -> User:
        """
        Create a new user with hashed password

        Args:
            email: User email
            password: Plain text password
            role: User role enum

        Returns:
            Created User object

        Raises:
            Exception: If user creation fails
        """
        # Generate username from email
        username = email.split('@')[0]

        # Check if username exists, make unique
        base_username = username
        counter = 1
        while await self.get_user_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        async with postgres_manager.get_session() as session:
            try:
                user = User(
                    username=username,
                    email=email,
                    hashed_password=self.hash_password(password),
                    role=role,
                    is_active=True
                )

                session.add(user)
                await session.commit()
                await session.refresh(user)

                print(f"[UserManager] Created user: {username} ({email})")
                return user

            except Exception as e:
                print(f"[UserManager] Failed to create user {email}: {e}")
                await session.rollback()
                raise

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email

        Args:
            email: User email

        Returns:
            User object or None
        """
        async with postgres_manager.get_session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username

        Args:
            username: Username

        Returns:
            User object or None
        """
        async with postgres_manager.get_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()

    # async def get_user_by_id(self, user_id: str) -> Optional[User]:
    #     """
    #     Get user by ID
    #
    #     Args:
    #         user_id: User ID (UUID as string)
    #
    #     Returns:
    #         User object or None
    #     """
    #     async with postgres_manager.get_session() as session:
    #         result = await session.execute(
    #             select(User).where(User.id == UUID(user_id))
    #         )
    #         return result.scalar_one_or_none()

    async def update_password(self, email: str, new_password: str) -> bool:
        """
        Update user password

        Args:
            email: User email
            new_password: New plain text password

        Returns:
            True if updated, False if user not found
        """
        user = await self.get_user_by_email(email)
        if not user:
            return False

        async with postgres_manager.get_session() as session:
            try:
                user.hashed_password = self.hash_password(new_password)
                session.add(user)
                await session.commit()

                print(f"[UserManager] Password updated for: {email}")
                return True

            except Exception as e:
                print(f"[UserManager] Failed to update password for {email}: {e}")
                await session.rollback()
                return False


# Singleton instance
user_manager = UserManager()