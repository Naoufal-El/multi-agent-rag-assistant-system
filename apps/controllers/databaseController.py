"""
Database administration endpoints
"""
from fastapi import APIRouter, HTTPException
from apps.repository.postgres_manager import postgres_manager
from apps.models.dto.schemas import DatabaseStatusResponse
from apps.middleware.auth_middleware import require_admin
from fastapi import Depends

router = APIRouter(prefix="/db")


@router.post("/init", dependencies=[Depends(require_admin)])
async def initialize_database() -> DatabaseStatusResponse:
    """
    Initialize PostgreSQL connection and create all tables
    This endpoint:
    - Initializes the async engine and connection pool
    - Imports all model classes
    - Creates tables if they don't exist
    - Returns status of operation
    """
    try:
        print("[ADMIN] Initializing database...")
        # Initialize the postgres client (creates engine, session factory)
        await postgres_manager.initialize()

        return {
            "status": "success",
            "message": "Database initialized and tables created/verified, Existing tables were not modified",
            "tables": list(postgres_manager.get_table_names())
        }

    except Exception as e:
        print(f"[ADMIN] Database initialization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize database: {str(e)}"
        )


@router.get("/status", dependencies=[Depends(require_admin)])
async def get_database_status() -> DatabaseStatusResponse:
    """Get current database connection status and table information"""
    try:
        # Check if initialized
        is_initialized = postgres_manager.engine is not None

        if not is_initialized:
            return {
                "status": "not_initialized",
                "message": "Database not initialized. Call /admin/init-db first",
                "tables": []
            }

        # Get table names
        tables = postgres_manager.get_table_names()

        return {
            "status": "initialized",
            "message": is_initialized,  # Just check if engine exists
            "tables": tables
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get database status: {str(e)}"
        )