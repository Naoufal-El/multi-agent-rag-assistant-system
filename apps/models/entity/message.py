import uuid
from datetime import datetime, UTC
from typing import Dict, Any
from sqlalchemy import Column, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from apps.models.entity.base import Base

class MessageService(Base):
    """Stores individual messages in conversations"""
    __tablename__ = "messages"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to conversation
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    role = Column(SQLEnum('user', 'assistant', 'system', name='message_role'), nullable=False)
    content = Column(Text, nullable=False)

    # Timestamp
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    # Flexible metadata (route used, retrieval context, tokens, etc.)
    msg_metadata = Column(JSONB, default=dict, nullable=True)

    # Relationships
    conversation = relationship("ConversationService", back_populates="messages")

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.msg_metadata
        }