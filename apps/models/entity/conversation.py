"""
Conversation Entity - Chat Session Management
NOW WITH USER ISOLATION
"""

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from apps.models.entity.base import Base
from datetime import datetime, UTC
import uuid


class ConversationService(Base):
    """
    Conversation model for chat sessions
    
    NOW USER-SCOPED: Each conversation belongs to a specific user
    """
    __tablename__ = "conversations"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User Ownership (NEW)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Thread identifier (scoped per user)
    thread_id = Column(String(255), nullable=False, index=True)

    # Metadata
    user_metadata = Column(JSON, default=dict)
    status = Column(String(50), default='active')

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    user = relationship("User", back_populates="conversations")  # NEW
    messages = relationship("MessageService", back_populates="conversation", cascade="all, delete-orphan")
    analytics = relationship("AnalyticsService", back_populates="conversation", uselist=False, cascade="all, delete-orphan")

    # Constraints: Unique (user_id, thread_id) combination
    __table_args__ = (
        UniqueConstraint('user_id', 'thread_id', name='uq_user_thread'),
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, thread={self.thread_id})>"