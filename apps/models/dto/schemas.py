from pydantic import BaseModel, Field
from typing import List, TypedDict
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    EMPLOYEE = "employee"
    CUSTOMER = "customer"


# NEW: Collection Type Enum for ingestion - Shows as dropdown in Swagger
class CollectionType(str, Enum):
    """Target collection for document ingestion"""
    customer_kb = "customer_kb"      # E-commerce products/electronics
    process_kb = "process_kb"         # HR/internal processes


class HealthDTO(BaseModel):
    status: str
    result: dict


class ChatRequest(BaseModel):
    """Chat request model with user type selection"""
    thread_id: str = Field(..., description="Unique conversation thread ID (required)")
    message: str = Field(..., description="User message")


class ChatDTO(BaseModel):
    thread_id: str
    message: str
    reply: str
    route: str
    health: dict
    turn_count: int
    loaded_history: int


class DatabaseStatusResponse(TypedDict):
    status: str
    message: str
    tables: List[str]


class ThreadActionResponse(TypedDict):
    success: bool
    message: str
    thread_id: str