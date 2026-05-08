from fastapi import APIRouter, HTTPException, Query
from apps.config.settings import settings
from apps.core.vector_store.qdrant_client import qdrant_store
from apps.models.dto.schemas import CollectionType
from apps.models.ingestion.response import CollectionInfoResponse
from apps.middleware.auth_middleware import require_admin
from fastapi import Depends

router = APIRouter(prefix="/vector")

# ============================================
# COLLECTION MANAGEMENT (NEW)
# ============================================

@router.post("/collection-create", dependencies=[Depends(require_admin)])
async def create_collection(
        collection_name: str,
        recreate: bool = False
):
    """
    Create a Qdrant collection

    Args:
        collection_name: Name of the collection to create
        recreate: If True, delete existing collection and recreate

    Examples:
        POST /ingestion/create-collection?collection_name=customer_kb
        POST /ingestion/create-collection?collection_name=process_collection&recreate=true
    """
    try:

        # Validate collection name
        valid_collections = [
            settings.qdrant.customer_collection,
            settings.qdrant.process_collection
        ]

        if collection_name not in valid_collections:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid collection name. Must be one of: {valid_collections}"
            )

        # Create collection
        print(f"[API] Creating collection: {collection_name} (recreate={recreate})")
        success = qdrant_store.create_collection(collection_name, recreate=recreate)

        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create collection: {collection_name}"
            )

        # Get collection info
        info = qdrant_store.get_collection_info(collection_name)

        return {
            "status": "success",
            "message": f"Collection '{collection_name}' created successfully",
            "collection_name": collection_name,
            "recreated": recreate,
            "info": info
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections-list", dependencies=[Depends(require_admin)])
async def list_collections():
    """
    List all available Qdrant collections

    Returns collection names and their statistics
    """
    try:

        collections = []

        # Check both collections
        for col_name in [settings.qdrant.customer_collection, settings.qdrant.process_collection]:
            try:
                info = qdrant_store.get_collection_info(col_name)
                if info:
                    collections.append({
                        "name": col_name,
                        "exists": True,
                        **info
                    })
                else:
                    collections.append({
                        "name": col_name,
                        "exists": False
                    })
            except Exception as e:
                collections.append({
                    "name": col_name,
                    "exists": False,
                    "error": str(e)
                })

        return {
            "status": "success",
            "collections": collections
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collection-info", response_model=CollectionInfoResponse, dependencies=[Depends(require_admin)])
async def get_collection_info(
        collection: CollectionType = Query(
            default=CollectionType.customer_kb,
            description="Collection to query (customer_kb or process_kb)"
        )
):
    """Get Qdrant collection statistics for specific collection"""
    try:
        info = qdrant_store.get_collection_info(collection.value)
        return CollectionInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))