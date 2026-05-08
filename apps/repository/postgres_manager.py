# apps/repository/postgres_manager.py

"""
PostgreSQL Manager - Long-term Memory & Persistence
Manages conversation history, messages, and analytics in PostgreSQL
"""

from typing import Optional, AsyncGenerator, List, Dict, Any
from contextlib import asynccontextmanager
from uuid import UUID
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy import exc, select, desc, and_, cast, Date
from apps.config.settings import settings
from datetime import datetime, UTC, timedelta

# Import Base and Models
from apps.models.entity.base import Base
from apps.models.entity.user import User
from apps.models.entity.conversation import ConversationService
from apps.models.entity.message import MessageService
from apps.models.entity.analytics import AnalyticsService


class PostgresManager:
    """
    PostgreSQL Manager for long-term conversation persistence
    
    Responsibilities:
    - Connection pool management
    - Conversation CRUD operations (USER-SCOPED)
    - Message persistence
    - Analytics tracking and updates
    - Historical conversation retrieval
    """

    def __init__(self):
        """Initialize PostgresManager with database URL from settings"""
        self.database_url = settings.db.url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

    async def initialize(self):
        """Initialize async engine and session factory"""
        if self.engine is not None:
            print("[PostgresManager] Already initialized")
            return

        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=settings.memory.postgres_pool_size,
                max_overflow=settings.memory.postgres_max_overflow,
                pool_pre_ping=True,
                pool_recycle=settings.memory.postgres_pool_recycle
            )
            print("[PostgresManager] Async engine created with connection pooling")

            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            print("[PostgresManager] Session factory created")

            await self.create_tables()
            print("[PostgresManager] Initialization complete")
        except Exception as e:
            print(f"[PostgresManager] Initialization failed: {e}")
            raise

    async def create_tables(self):
        """Create all tables defined in SQLAlchemy models"""
        if self.engine is None:
            raise RuntimeError("Engine not initialized. Call initialize() first.")

        try:
            registered_tables = list(Base.metadata.tables.keys())
            print(f"[PostgresManager] Found {len(registered_tables)} registered models")
            print(f"[PostgresManager] Tables: {registered_tables}")

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            print("[PostgresManager] Tables created/verified successfully")
        except Exception as e:
            print(f"[PostgresManager] Error creating tables: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an async database session as a context manager"""
        if self.session_factory is None:
            raise RuntimeError("PostgresManager not initialized. Call initialize() first.")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except exc.SQLAlchemyError as e:
                await session.rollback()
                print(f"[PostgresManager] Transaction rolled back: {e}")
                raise
            finally:
                await session.close()

    # ==================== CONVERSATION OPERATIONS (USER-SCOPED) ====================

    async def get_or_create_conversation(
            self,
            thread_id: str,
            user_id: Optional[str] = None,
            user_metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationService:
        """
        Get existing conversation or create new one (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier (can be combined "user_id:thread_id" format)
            user_id: User identifier (extracted if not provided)
            user_metadata: Optional metadata
        
        Returns:
            ConversationService instance
        """
        async with self.get_session() as session:
            # Parse user_id from thread_id if not provided
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            if not user_id:
                raise ValueError("user_id is required (either directly or in thread_id format)")

            # Query by BOTH user_id AND thread_id
            query = select(ConversationService).where(
                and_(
                    ConversationService.user_id == UUID(user_id),
                    ConversationService.thread_id == actual_thread_id
                )
            )

            result = await session.execute(query)
            conversation = result.scalar_one_or_none()

            if conversation:
                print(f"[PostgresManager] Found existing conversation: user={user_id}, thread={actual_thread_id}")
                return conversation

            # Create new conversation
            conversation = ConversationService(
                user_id=UUID(user_id),
                thread_id=actual_thread_id,
                user_metadata=user_metadata or {},
                status='active'
            )
            session.add(conversation)

            # FLUSH to get the conversation.id assigned by database
            await session.flush()

            # Create associated analytics record
            analytics = AnalyticsService(
                conversation_id=conversation.id,
                total_messages=0,
                total_turns=0,
                routes_used={}
            )
            session.add(analytics)
            await session.commit()
            await session.refresh(conversation)

            print(f"[PostgresManager] Created new conversation: user={user_id}, thread={actual_thread_id}")
            return conversation

    async def get_conversation(
            self,
            thread_id: str,
            user_id: Optional[str] = None
    ) -> Optional[ConversationService]:
        """
        Get conversation by thread_id and user_id (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier
            user_id: User identifier (extracted if not provided)
        
        Returns:
            ConversationService or None
        """
        async with self.get_session() as session:
            # Parse user_id from thread_id if not provided
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            if not user_id:
                # Fallback: search by thread_id only (legacy behavior)
                query = select(ConversationService).where(
                    ConversationService.thread_id == actual_thread_id
                )
            else:
                # Filter by BOTH user_id and thread_id
                query = select(ConversationService).where(
                    and_(
                        ConversationService.user_id == UUID(user_id),
                        ConversationService.thread_id == actual_thread_id
                    )
                )

            result = await session.execute(query)
            return result.scalar_one_or_none()

    # ==================== MESSAGE OPERATIONS ====================

    async def save_messages(
            self,
            conversation_id: str,  # Format: "user_id:thread_id"
            messages: List[Dict[str, Any]],
            route_used: Optional[str] = None
    ) -> int:
        """
        Save multiple messages to a conversation
        
        Args:
            conversation_id: Combined ID in format "user_id:thread_id"
            messages: List of message dicts
            route_used: Route taken (for analytics)
        
        Returns:
            Number of messages saved
        """
        async with self.get_session() as session:
            # Parse conversation_id
            if ":" in conversation_id:
                user_id_str, thread_id = conversation_id.split(":", 1)
            else:
                # Fallback
                user_id_str = conversation_id
                thread_id = conversation_id

            # Get or create conversation
            conversation = await self.get_or_create_conversation(
                thread_id=thread_id,
                user_id=user_id_str
            )

            saved_count = 0
            for msg in messages:
                message = MessageService(
                    conversation_id=conversation.id,
                    role=msg.get('role', 'user'),
                    content=msg.get('content', ''),
                    msg_metadata=msg.get('metadata', {})
                )
                session.add(message)
                saved_count += 1

            # Update analytics
            if route_used:
                await self._update_analytics(
                    session,
                    conversation.id,
                    message_count=saved_count,
                    route=route_used
                )

            await session.commit()
            print(f"[PostgresManager] Saved {saved_count} messages for {conversation_id}")
            return saved_count

    async def load_conversation_history(
            self,
            thread_id: str,
            user_id: Optional[str] = None,  # ← ADD user_id parameter
            limit: Optional[int] = None,
            include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Load conversation history from PostgreSQL (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier (can be "user_id:thread_id" format)
            user_id: User identifier (extracted if not provided)
            limit: Max messages to return
            include_metadata: Include message metadata
        
        Returns:
            List of message dicts
        """
        async with self.get_session() as session:
            # Parse user_id from thread_id if not provided
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            # Get conversation with user_id filtering
            conversation = await self.get_conversation(actual_thread_id, user_id)

            if not conversation:
                print(f"[PostgresManager] No conversation found: user={user_id}, thread={actual_thread_id}")
                return []

            # Build query for messages
            query = select(MessageService).where(
                MessageService.conversation_id == conversation.id
            ).order_by(MessageService.timestamp.asc())

            if limit:
                query = query.limit(limit)

            # Execute query
            result = await session.execute(query)
            messages = result.scalars().all()

            # Convert to dict format
            history = []
            for msg in messages:
                msg_dict = {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                }
                if include_metadata:
                    msg_dict['metadata'] = msg.msg_metadata
                history.append(msg_dict)

            print(f"[PostgresManager] Loaded {len(history)} messages for user={user_id}, thread={actual_thread_id}")
            return history

    async def get_recent_messages(
            self,
            thread_id: str,
            user_id: Optional[str] = None,  # ← ADD user_id parameter
            count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most recent N messages from a conversation (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier
            user_id: User identifier
            count: Number of recent messages
        
        Returns:
            List of message dicts (chronological order)
        """
        async with self.get_session() as session:
            # Parse user_id from thread_id if not provided
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            # Get conversation with user filtering
            conversation = await self.get_conversation(actual_thread_id, user_id)

            if not conversation:
                return []

            # Get recent messages
            query = (
                select(MessageService)
                .where(MessageService.conversation_id == conversation.id)
                .order_by(desc(MessageService.timestamp))
                .limit(count)
            )

            result = await session.execute(query)
            messages = result.scalars().all()

            # Return in chronological order (oldest to newest)
            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in reversed(list(messages))
            ]

    # ==================== USER THREAD LISTING (NEW) ====================

    async def list_user_threads(
            self,
            user_id: str,
            start_date: Optional[str] = None,  # Format: "YYYY-MM-DD"
            end_date: Optional[str] = None,    # Format: "YYYY-MM-DD"
            limit: int = 100,
            offset: int = 0,
            include_analytics: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all conversation threads for a specific user with date filtering

        Args:
            user_id: User identifier
            start_date: Start date (YYYY-MM-DD format) - defaults to 30 days ago
            end_date: End date (YYYY-MM-DD format) - defaults to today
            limit: Maximum threads to return
            offset: Number of threads to skip
            include_analytics: Include analytics data

        Returns:
            List of thread dicts with metadata and first message
        """
        async with self.get_session() as session:
            # Calculate default date range if not provided
            if not end_date:
                end_date_obj = datetime.now(UTC).date()
            else:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()

            if not start_date:
                # Default: 30 days before end_date
                start_date_obj = end_date_obj - timedelta(days=30)
            else:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()

            print(f"[PostgresManager] Listing threads for user={user_id}, date range: {start_date_obj} to {end_date_obj}")

            # Query conversations within date range (DATE-ONLY comparison)
            query = (
                select(ConversationService)
                .where(
                    and_(
                        ConversationService.user_id == UUID(user_id),
                        ConversationService.status != 'deleted',
                        # DATE-ONLY comparison (ignore time)
                        cast(ConversationService.created_at, Date) >= start_date_obj,
                        cast(ConversationService.created_at, Date) <= end_date_obj
                    )
                )
                .order_by(desc(ConversationService.updated_at))
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            conversations = result.scalars().all()

            if not conversations:
                print(f"[PostgresManager] No threads found for user={user_id} in date range")
                return []

            threads = []
            for conv in conversations:
                thread_data = {
                    'thread_id': conv.thread_id,
                    'status': conv.status,
                    'created_at': conv.created_at.isoformat(),
                    'updated_at': conv.updated_at.isoformat(),
                    'user_metadata': conv.user_metadata
                }

                # Get first message (user or assistant only, exclude system)
                first_msg_query = (
                    select(MessageService)
                    .where(
                        and_(
                            MessageService.conversation_id == conv.id,
                            MessageService.role.in_(['user', 'assistant'])
                        )
                    )
                    .order_by(MessageService.timestamp.asc())
                    .limit(1)
                )

                first_msg_result = await session.execute(first_msg_query)
                first_message = first_msg_result.scalar_one_or_none()

                if first_message:
                    thread_data['first_message'] = {
                        'role': first_message.role,
                        'content': first_message.content[:200],  # Truncate to 200 chars
                        'timestamp': first_message.timestamp.isoformat()
                    }
                else:
                    thread_data['first_message'] = None

                # Optionally include analytics
                if include_analytics:
                    analytics_query = select(AnalyticsService).where(
                        AnalyticsService.conversation_id == conv.id
                    )
                    analytics_result = await session.execute(analytics_query)
                    analytics = analytics_result.scalar_one_or_none()

                    if analytics:
                        thread_data['analytics'] = {
                            'total_messages': analytics.total_messages,
                            'total_turns': analytics.total_turns,
                            'routes_used': analytics.routes_used
                        }

                threads.append(thread_data)

            print(f"[PostgresManager] Listed {len(threads)} threads for user={user_id}")
            return threads


    # ==================== ANALYTICS OPERATIONS ====================

    async def _update_analytics(
            self,
            session: AsyncSession,
            conversation_id: UUID,
            message_count: int = 0,
            route: Optional[str] = None,
            response_time_ms: Optional[int] = None
    ):
        """Internal method to update conversation analytics"""
        query = select(AnalyticsService).where(
            AnalyticsService.conversation_id == conversation_id
        )

        result = await session.execute(query)
        analytics = result.scalar_one_or_none()

        if not analytics:
            analytics = AnalyticsService(
                conversation_id=conversation_id,
                total_messages=0,
                total_turns=0,
                routes_used={}
            )
            session.add(analytics)

        # Update message count
        analytics.total_messages += message_count

        # Update turn count
        analytics.total_turns = analytics.total_messages // 2

        # Update route usage
        if route:
            routes = analytics.routes_used or {}
            routes[route] = routes.get(route, 0) + 1
            analytics.routes_used = routes

        # Update average response time
        if response_time_ms:
            if analytics.avg_response_time_ms:
                total_turns = analytics.total_turns
                current_avg = analytics.avg_response_time_ms
                analytics.avg_response_time_ms = int(
                    (current_avg * (total_turns - 1) + response_time_ms) / total_turns
                )
            else:
                analytics.avg_response_time_ms = response_time_ms

    async def get_analytics(
            self,
            thread_id: str,
            user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get analytics for a conversation (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier
            user_id: User identifier
        
        Returns:
            Analytics dict or None
        """
        async with self.get_session() as session:
            # Parse user_id if needed
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            # Get conversation with user filtering
            conversation = await self.get_conversation(actual_thread_id, user_id)

            if not conversation:
                return None

            query = select(AnalyticsService).where(
                AnalyticsService.conversation_id == conversation.id
            )

            result = await session.execute(query)
            analytics = result.scalar_one_or_none()

            if not analytics:
                return None

            return {
                'total_messages': analytics.total_messages,
                'total_turns': analytics.total_turns,
                'avg_response_time_ms': analytics.avg_response_time_ms,
                'routes_used': analytics.routes_used
            }

    # ==================== SOFT DELETE OPERATIONS ====================

    async def soft_delete_conversation(
            self,
            thread_id: str,
            user_id: Optional[str] = None
    ) -> bool:
        """
        Soft delete a conversation (USER-SCOPED)
        
        Args:
            thread_id: Thread identifier
            user_id: User identifier (for validation)
        
        Returns:
            True if deleted, False if not found
        """
        async with self.get_session() as session:
            # Parse user_id if needed
            if not user_id and ":" in thread_id:
                user_id, actual_thread_id = thread_id.split(":", 1)
            else:
                actual_thread_id = thread_id

            # SECURE: Get conversation with user filtering
            conversation = await self.get_conversation(actual_thread_id, user_id)

            if not conversation:
                print(f"[PostgresManager] Conversation not found: user={user_id}, thread={actual_thread_id}")
                return False

            if conversation.status == 'deleted':
                print(f"[PostgresManager] Conversation already deleted")
                return True

            # Update status to deleted
            conversation.status = 'deleted'
            conversation.updated_at = datetime.now(UTC)

            await session.commit()
            print(f"[PostgresManager] Soft deleted conversation: user={user_id}, thread={actual_thread_id}")
            return True

    # ==================== ADMIN & UTILITY OPERATIONS ====================

    def get_table_names(self) -> list:
        """Get list of all table names registered in metadata"""
        return list(Base.metadata.tables.keys())

    async def close(self):
        """Close database connection pool and cleanup resources"""
        if self.engine:
            await self.engine.dispose()
            print("[PostgresManager] Connection pool closed")
            self.engine = None
            self.session_factory = None


# Singleton instance
postgres_manager = PostgresManager()