import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from apps.controllers import healthController, chatController, databaseController, ingestionController, collectionController, authController
from contextlib import asynccontextmanager
from apps.repository.redis_manager import redis_manager
from apps.repository.postgres_manager import postgres_manager
from apps.ingestion.jobs.background_worker import background_worker
from apps.utils.directory_manager import directory_manager
from apps.config.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Handles startup and shutdown events:
    - Startup: Initialize connections, resources
    - Shutdown: Gracefully close all connections
    """
    # =========================
    # STARTUP
    # =========================
    print("[APP] Application starting up...")

    # Initialize PostgreSQL connection and create tables
    try:
        await postgres_manager.initialize()
        print("[APP] PostgreSQL initialized successfully")
    except Exception as e:
        print(f"[APP] WARNING: PostgreSQL initialization failed: {e}")
        print("[APP] You can initialize manually via /database/init-db")

    # Create ingestion directories
    try:
        directory_manager.create_directories()
        print("[APP] Ingestion directories created/verified")
    except Exception as e:
        print(f"[APP] WARNING: Directory creation failed: {e}")

    # Start background worker
    if settings.ingestion.auto_scan_enabled:
        try:
            await background_worker.start()
            print("[APP] Background worker started (auto_scan_enabled=true)")
        except Exception as e:
            print(f"[APP] WARNING: Background worker failed to start: {e}")
    else:
        print("[APP] Background worker NOT started (auto_scan_enabled=false)")
        print("[APP] Use POST /ingestion/worker/start to start it manually")

    print("[APP] Startup complete")

    # Application is now running
    yield

    # =========================
    # SHUTDOWN
    # =========================
    print("[APP] Application shutting down...")

    # Stop background worker
    try:
        await background_worker.stop()
        print("[APP] Background worker stopped")
    except Exception as e:
        print(f"[APP] Error stopping background worker: {e}")

    # Close PostgreSQL connections
    try:
        print("[APP] Closing PostgreSQL connection pool...")
        await postgres_manager.close()
        print("[APP] PostgreSQL connections closed")
    except Exception as e:
        print(f"[APP] Error closing PostgreSQL: {e}")

    # Close Redis connections
    try:
        print("[APP] Closing Redis connection...")
        await redis_manager.close()
        print("[APP] Redis connection closed")
    except Exception as e:
        print(f"[APP] Error closing Redis: {e}")

    print("[APP] Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Agentic Assistant API",
    description="AI-powered customer service assistant with RAG, guardrails, and role-based access control",
    version="0.2.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Routers
app.include_router(healthController.router, tags=["Health"])
app.include_router(authController.router, tags=["Authentication"])
app.include_router(chatController.router, tags=["Chat"])
app.include_router(databaseController.router, tags=["Database"])
app.include_router(collectionController.router, tags=["Collections"])
app.include_router(ingestionController.router, tags=["Ingestion"])


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")

# Start the application with Uvicorn
if __name__ == "__main__":
    uvicorn.run("apps.main:app", host="localhost", port=8000, reload=True, workers=1, log_level="debug")