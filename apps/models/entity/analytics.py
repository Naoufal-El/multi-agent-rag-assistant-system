import uuid
from datetime import datetime, UTC
from typing import Dict, Any
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from apps.models.entity.base import Base

class AnalyticsService(Base):
    """Stores conversation analytics and metrics"""
    __tablename__ = "analytics"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to conversation (one-to-one)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Metrics
    total_messages = Column(Integer, default=0, nullable=False)
    total_turns = Column(Integer, default=0, nullable=False)
    avg_response_time_ms = Column(Integer, default=0, nullable=True)

    # Route usage tracking (e.g., {"cs_answer": 5, "cs_rag": 3})
    routes_used = Column(JSONB, default=dict, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    conversation = relationship("ConversationService", back_populates="analytics")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "total_messages": self.total_messages,
            "total_turns": self.total_turns,
            "avg_response_time_ms": self.avg_response_time_ms,
            "routes_used": self.routes_used,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }