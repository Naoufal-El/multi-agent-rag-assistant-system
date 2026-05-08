"""
Hybrid Memory Manager - Unified Memory Interface
Combines Redis (fast cache) + PostgreSQL (durable storage)

Strategy:
- Load: Try Redis first, fallback to PostgreSQL, warm cache if needed
- Save: Write to Redis immediately, async write to PostgreSQL
"""

from typing import List, Dict, Optional, Any
from apps.config.settings import settings
from apps.repository.redis_manager import redis_manager
from apps.repository.postgres_manager import postgres_manager


class HybridMemoryManager:
    """
    Unified memory interface with Redis-first caching and PostgreSQL persistence
    """

    def __init__(self):
        """Initialize HybridMemoryManager with settings from memory_conf.yaml"""
        self.strategy = settings.memory.strategy
        self.redis_ttl_days = settings.memory.redis_ttl_days
        self.max_history_from_db = settings.memory.max_history_from_db
        self.cache_warm_on_load = settings.memory.cache_warm_on_load

        print(f"[HybridMemoryManager] Initialized")
        print(f"[HybridMemoryManager] Strategy: {self.strategy}")
        print(f"[HybridMemoryManager] Redis TTL: {self.redis_ttl_days} days")
        print(f"[HybridMemoryManager] Max DB History: {self.max_history_from_db} messages")
        print(f"[HybridMemoryManager] Cache Warming: {'enabled' if self.cache_warm_on_load else 'disabled'}")

    async def load_history(
            self,
            user_id: str,  # ← RENAMED from thread_id to match usage
            thread_id: str,
            warm_cache: Optional[bool] = None
    ) -> List[Dict[str, str]]:
        """
        Smart load: Redis → PostgreSQL → Empty
        
        Args:
            user_id: User identifier
            thread_id: Thread/conversation identifier
            warm_cache: Override default cache warming behavior
            
        Returns:
            List of message dicts with 'role', 'content', 'timestamp'
        """
        should_warm = warm_cache if warm_cache is not None else self.cache_warm_on_load

        cache_key = f"{user_id}:{thread_id}"
        print(f"[HybridMemory] Loading history for user={user_id}, thread={thread_id}")

        # STEP 1: Try Redis (Fast Path)
        history = await redis_manager.load_history(cache_key)
        if history:
            print(f"[HybridMemory] Cache HIT - Loaded {len(history)} messages from Redis")
            return history

        # STEP 2: Try PostgreSQL (Slow Path)
        print(f"[HybridMemory] Cache MISS - Checking PostgreSQL...")

        try:
            # FIX: Use combined conversation_id format that matches save_messages
            conversation_id = cache_key  # "user_id:thread_id"

            history = await postgres_manager.load_conversation_history(
                conversation_id,  # ← FIXED: positional argument
                limit=self.max_history_from_db
            )

            if history:
                print(f"[HybridMemory] Database HIT - Loaded {len(history)} messages from PostgreSQL")

                # STEP 3: Warm Redis Cache
                if should_warm:
                    print(f"[HybridMemory] Warming cache for {cache_key}")
                    try:
                        await redis_manager.save_messages(
                            cache_key,
                            messages=history,
                            ttl_days=self.redis_ttl_days
                        )
                        print(f"[HybridMemory] Cache warmed successfully")
                    except Exception as e:
                        print(f"[HybridMemory] Cache warming failed: {e}")

                return history

        except Exception as e:
            print(f"[HybridMemory] PostgreSQL load failed: {e}")

        # STEP 4: Not Found Anywhere
        print(f"[HybridMemory] No history found for {cache_key} (new conversation)")
        return []

    # hybrid_memory_manager.py

    async def save_messages(
            self,
            user_id: str,
            thread_id: str,
            messages: List[Dict[str, str]],
            route_used: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Dual-write: Save to both Redis and PostgreSQL

        Args:
            user_id: User identifier
            thread_id: Thread/conversation identifier
            messages: List of NEW messages to save
            route_used: Route taken by orchestrator (for analytics)

        Returns:
            Dict with status of both writes: {"redis": bool, "postgres": bool}
        """
        cache_key = f"{user_id}:{thread_id}"
        print(f"[HybridMemory] Saving {len(messages)} NEW messages for {cache_key}")

        results = {
            "redis": False,
            "postgres": False
        }

        # ✅ FIX: Load existing messages, append new ones, then REPLACE in Redis
        try:
            # Load existing history from Redis
            existing_history = await redis_manager.load_history(cache_key) or []
            print(f"[HybridMemory] Loaded {len(existing_history)} existing messages from Redis")

            # Combine existing + new messages
            updated_history = existing_history + messages
            print(f"[HybridMemory] Total history after append: {len(updated_history)} messages")

            # Write COMPLETE history to Redis with REPLACE mode
            success = await redis_manager.save_messages(
                cache_key,
                messages=updated_history,  # ← ALL messages
                ttl_days=self.redis_ttl_days,
                replace=True  # ← ✅ CRITICAL: Delete old data first
            )

            results["redis"] = success
            if success:
                print(f"[HybridMemory] Redis write SUCCESS ({len(updated_history)} total messages)")
            else:
                print(f"[HybridMemory] Redis write returned False")
        except Exception as e:
            print(f"[HybridMemory] Redis write FAILED: {e}")

        # Write NEW messages to PostgreSQL
        try:
            count = await postgres_manager.save_messages(
                cache_key,  # Use cache_key as conversation_id
                messages=messages,  # ← Only NEW messages
                route_used=route_used
            )
            results["postgres"] = count > 0
            if count > 0:
                print(f"[HybridMemory] PostgreSQL write SUCCESS ({count} new messages)")
            else:
                print(f"[HybridMemory] PostgreSQL write returned 0 messages")
        except Exception as e:
            print(f"[HybridMemory] PostgreSQL write FAILED: {e}")

        return results

    async def get_recent_messages(
            self,
            user_id: str,
            thread_id: str,
            count: int = 10
    ) -> List[Dict[str, str]]:
        """Get N most recent messages (prioritizes Redis for speed)"""
        history = await self.load_history(user_id, thread_id)
        return history[-count:] if history else []

    async def clear_history(
            self,
            user_id: str,
            thread_id: str,
            clear_db: bool = False
    ) -> Dict[str, bool]:
        """Clear conversation history"""
        cache_key = f"{user_id}:{thread_id}"
        print(f"[HybridMemory] Clearing history for {cache_key} (clear_db={clear_db})")

        results = {
            "redis": False,
            "postgres": False
        }

        # Clear Redis cache
        try:
            success = await redis_manager.clear_history(cache_key)
            results["redis"] = success
            print(f"[HybridMemory] Redis clear: {'SUCCESS' if success else 'FAILED'}")
        except Exception as e:
            print(f"[HybridMemory] Redis clear failed: {e}")

        # Optionally delete from PostgreSQL
        if clear_db:
            try:
                success = await postgres_manager.soft_delete_conversation(cache_key)
                results["postgres"] = success
                if success:
                    print(f"[HybridMemory] PostgreSQL soft delete: SUCCESS")
                else:
                    print(f"[HybridMemory] PostgreSQL soft delete: conversation not found")
            except Exception as e:
                print(f"[HybridMemory] PostgreSQL soft delete failed: {e}")

        return results

    async def get_analytics(self, user_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation analytics from PostgreSQL"""
        cache_key = f"{user_id}:{thread_id}"
        try:
            analytics = await postgres_manager.get_analytics(cache_key)
            if analytics:
                print(f"[HybridMemory] Retrieved analytics for {cache_key}")
            else:
                print(f"[HybridMemory] No analytics found for {cache_key}")
            return analytics
        except Exception as e:
            print(f"[HybridMemory] Failed to get analytics for {cache_key}: {e}")
            return None

    def get_config(self) -> Dict[str, Any]:
        """Get current hybrid memory configuration"""
        return {
            "strategy": self.strategy,
            "redis_ttl_days": self.redis_ttl_days,
            "max_history_from_db": self.max_history_from_db,
            "cache_warm_on_load": self.cache_warm_on_load,
        }


# Singleton instance
hybrid_memory_manager = HybridMemoryManager()