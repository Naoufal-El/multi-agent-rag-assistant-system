"""
Chat Controller - Handles chat interactions and thread management
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import Optional
from apps.models.dto.schemas import ChatRequest, ChatDTO, ThreadActionResponse
from apps.services.chatService import chatService
from apps.repository.memory.hybrid_memory_manager import hybrid_memory_manager
from apps.services.HealthService import healthService
from apps.middleware.auth_middleware import get_current_user, require_admin
from apps.repository.postgres_manager import postgres_manager

router = APIRouter()

# ========================================
# PUBLIC ENDPOINT (All authenticated users)
# ========================================

@router.post("/chat", response_model=ChatDTO)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Chat endpoint - accessible to all authenticated users

    - Customers: Use customer_kb only
    - Employees: Use process_kb + customer_kb + conversation agent
    - Admin: Same as employee (full access)

    Users can only access their own conversation threads.
    """
    try:
        # Extract user_id and thread_id
        user_id = user['id']
        thread_id = request.thread_id
        combined_thread_id = f"{user_id}:{thread_id}"

        print(f"[CONTROLLER] 👤 User: {user['email']} (ID: {user_id}, Role: {user['role']})")
        print(f"[CONTROLLER] 🔗 Thread ID: {thread_id}")
        print(f"[CONTROLLER] 🔗 Combined Thread ID: {combined_thread_id}")

        # Load Conversation from Memory
        # ⚠️ FIX: Pass user_id and thread_id as separate arguments
        history = await hybrid_memory_manager.load_history(user_id, thread_id)

        # Track the original history length for later
        original_history_length = len(history)
        print(f"[CONTROLLER] 📜 Loaded {original_history_length} messages from history")

        # Add new user message to history
        new_message = {"role": "user", "content": request.message}
        history.append(new_message)

        # Turn count = number of user messages so far
        turn_count = sum(1 for msg in history if msg.get("role") == "user")

        # Create state for LangGraph
        # Map admin role to employee for routing purposes
        user_type = user["role"] if user["role"] != "admin" else "employee"

        state = {
            "thread_id": combined_thread_id,
            "messages": history,
            "user_type": user_type,
            "meta": {},
            "turn_count": turn_count,
            "loaded_from_memory": original_history_length > 0
        }

        # Health check before processing
        print("[CONTROLLER] Running health check...")
        health = await healthService.health_check()

        # Check critical services (Ollama is required for LLM responses)
        if health.get("ollama") != "ok":
            print(f"[CONTROLLER] ❌ Ollama is down: {health.get('ollama')}")
            raise HTTPException(
                status_code=503,
                detail="LLM service (Ollama) is unavailable"
            )

        # Warn about other services but continue
        other_issues = [s for s in ["redis", "postgres", "qdrant"]
                        if health.get(s) != "ok"]
        if other_issues:
            print(f"[CONTROLLER] ⚠️ Non-critical services degraded: {other_issues}")
        else:
            print(f"[CONTROLLER] ✅ All services healthy")

        # Invoke graph with supervision
        print(f"[CONTROLLER] Starting graph execution...")
        result = await chatService.invoke_with_supervision(state)
        print("[CONTROLLER] Graph execution completed successfully")

        # Extract final response
        all_messages = result.get("messages", [])
        if not all_messages:
            raise HTTPException(500, "No response generated")

        last_message = all_messages[-1]
        response_text = last_message.get("content", "No response")
        route = result.get("route", "unknown")

        print(f"[CONTROLLER] 📤 Response generated via route: {route}")

        # Save new messages to memory (if not blocked)
        if route != "blocked":
            new_messages = all_messages[original_history_length:]
            if new_messages:
                await hybrid_memory_manager.save_messages(
                    user_id=user_id,
                    thread_id=thread_id,
                    messages=new_messages,
                    route_used=route
                )
                print(f"[CONTROLLER] 💾 Saved {len(new_messages)} messages")

        # Build response according to ChatDTO schema
        return ChatDTO(
            thread_id=request.thread_id,
            message=request.message,  # User's original message
            reply=response_text,  # Assistant's reply
            route=route,
            health=result.get("meta", {}),  # Metadata/health info
            turn_count=turn_count,
            loaded_history=original_history_length
        )

    except Exception as e:
        print(f"[CONTROLLER] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Chat processing failed: {str(e)}")

# ========================================
# ADMIN-ONLY ENDPOINTS (Thread management)
# ========================================

@router.get("/thread/{thread_id}/history", dependencies=[Depends(get_current_user)])
async def get_thread_history(thread_id: str, user: dict = Depends(get_current_user)):
    """
    Get conversation history for a thread - ADMIN ONLY

    Admins can view their own conversation history.
    """
    try:
        user_id = user['id']

        print(f"[CONTROLLER] Fetching history: user={user['email']}, thread={thread_id}")

        # Pass user_id and thread_id as separate arguments
        history = await hybrid_memory_manager.load_history(user_id, thread_id)

        # FILTER: Remove system messages
        filtered_messages = [
            msg for msg in history
            if msg.get('role') != 'system'
        ]

        return {
            "thread_id": thread_id,
            "user_id": user_id,
            "messages": filtered_messages,
            "count": len(filtered_messages)
        }

    except Exception as e:
        raise HTTPException(500, f"Failed to load history: {str(e)}")


@router.delete("/thread/{thread_id}", response_model=ThreadActionResponse, dependencies=[Depends(require_admin)])
async def delete_thread(thread_id: str, user: dict = Depends(get_current_user)):
    """
    Delete a conversation thread - ADMIN ONLY

    Admins can delete their own threads.
    """
    try:
        user_id = user['id']

        # ⚠️ FIX: Pass user_id and thread_id as separate arguments
        await hybrid_memory_manager.clear_history(user_id, thread_id, clear_db=True)

        return ThreadActionResponse(
            success=True,
            message=f"Thread {thread_id} deleted successfully",
            thread_id=thread_id
        )

    except Exception as e:
        raise HTTPException(500, f"Failed to delete thread: {str(e)}")


@router.get("/threads")
async def list_user_threads(
        start_date: Optional[str] = None,  # Query param: ?start_date=2025-07-06
        end_date: Optional[str] = None,    # Query param: ?end_date=2025-07-10
        limit: int = 100,
        user: dict = Depends(get_current_user)
):
    """
    List all conversation threads for current user with date filtering

    Query Parameters:
    - start_date: Start date in YYYY-MM-DD format (default: 30 days ago)
    - end_date: End date in YYYY-MM-DD format (default: today)
    - limit: Maximum threads to return (default: 100)

    Returns:
    - List of threads with first message preview
    - Empty list with message if no threads found in date range

    Examples:
    - GET /threads (last 30 days)
    - GET /threads?start_date=2025-07-06&end_date=2025-07-10
    - GET /threads?start_date=2025-01-01
    """
    try:
        user_id = user['id']

        # Validate date formats if provided
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(400, "Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(400, "Invalid end_date format. Use YYYY-MM-DD")

        print(f"[CONTROLLER] Listing threads: user={user['email']}, start={start_date}, end={end_date}")

        # Call postgres_manager with date filters
        threads = await postgres_manager.list_user_threads(
            user_id=str(user_id),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_analytics=True
        )

        # Handle empty result
        if not threads:
            return {
                "user_id": str(user_id),
                "threads": [],
                "count": 0,
                "message": "No threads found in the specified date range",
                "date_range": {
                    "start": start_date or "(30 days ago)",
                    "end": end_date or "(today)"
                }
            }

        return {
            "user_id": str(user_id),
            "threads": threads,
            "count": len(threads),
            "date_range": {
                "start": start_date or "(30 days ago)",
                "end": end_date or "(today)"
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONTROLLER] ❌ Error listing threads: {str(e)}")
        raise HTTPException(500, f"Failed to list threads: {str(e)}")