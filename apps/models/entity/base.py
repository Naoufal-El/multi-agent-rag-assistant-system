"""
Shared declarative base for all SQLAlchemy models
"""
from sqlalchemy.orm import declarative_base

# Single shared base for all models
Base = declarative_base()