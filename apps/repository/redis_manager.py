import json
from typing import List, Dict, Optional, Any
from datetime import datetime, UTC
import redis.asyncio as redis
from apps.config.settings import settings

class RedisManager:
    def __init__(self):
        self.redis_url = settings.redis.url
        self.max_history = settings.llm.max_history_msgs
        self.redis_ttl_days = settings.memory.redis_ttl_days
        self.history_buffer = settings.memory.redis_max_history_buffer
        self.redis_client: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis client"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client

    @staticmethod
    def _make_key(session_id: str) -> str:
        """Create Redis key for a session"""
        return f"chat:thread:{session_id}"

    async def load_history(self, thread_id: str) -> List[Dict[str, str]]:
        """
        Load conversation history from Redis

        Args:
            thread_id: Unique conversation identifier

        Returns:
            List of message dicts with 'role' and 'content'
        """
        try:
            r = await self._get_redis()
            key = self._make_key(thread_id)

            # Get all messages for this thread (stored as JSON strings)
            messages_json = await r.lrange(key, 0, -1)

            if not messages_json:
                return []

            # Parse JSON strings back to dicts
            messages = [json.loads(msg) for msg in messages_json]

            # Return only the last N messages (configured limit)
            return messages[-self.max_history:]

        except Exception as e:
            print(f"[MemoryManager] Error loading history for {thread_id}: {e}")
            return []

    async def save_messages(
            self,
            thread_id: str,
            messages: List[Dict[str, str]],
            ttl_days: Optional[int] = None,
            replace: bool = True
    ) -> bool:
        """
        Save messages to Redis

        Args:
            thread_id: Unique conversation identifier
            messages: List of messages (REPLACES all if replace=True, APPENDS if False)
            replace: If True, clear existing messages first (default: True)

        Returns:
            True if successful, False otherwise
        """
        try:
            r = await self._get_redis()
            key = self._make_key(thread_id)

            # ✅ REPLACE MODE: Delete existing key first
            if replace:
                await r.delete(key)

            # Append each message as JSON string
            for msg in messages:
                # Add timestamp if not present
                if "timestamp" not in msg:
                    msg["timestamp"] = datetime.now(UTC).isoformat()

                msg_json = json.dumps(msg)
                await r.rpush(key, msg_json)

            # Set expiration (30 days for inactive threads)
            await r.expire(key, 60 * 60 * 24 * 30)

            # Trim to prevent unbounded growth
            await r.ltrim(key, -(self.max_history * 2), -1)

            return True

        except Exception as e:
            print(f"[MemoryManager] Error saving messages for {thread_id}: {e}")
            return False

    async def clear_history(self, thread_id: str) -> bool:
        """
        Clear conversation history for a thread

        Args:
            thread_id: Unique conversation identifier

        Returns:
            True if successful
        """
        try:
            r = await self._get_redis()
            key = self._make_key(thread_id)
            deleted = await r.delete(key)
            return deleted > 0
        except Exception as e:
            print(f"[MemoryManager] Error clearing history for {thread_id}: {e}")
            return False

    async def get_thread_info(self, thread_id: str) -> Dict[str, Any]:
        """
        Get metadata about a conversation thread

        Args:
            thread_id: Unique conversation identifier

        Returns:
            Dict with message_count, created_at, etc.
        """
        try:
            r = await self._get_redis()
            key = self._make_key(thread_id)

            count = await r.llen(key)
            ttl = await r.ttl(key)

            return {
                "thread_id": thread_id,
                "message_count": count,
                "ttl_seconds": ttl if ttl > 0 else None,
                "exists": count > 0
            }
        except Exception as e:
            print(f"[MemoryManager] Error getting thread info for {thread_id}: {e}")
            return {"thread_id": thread_id, "message_count": 0, "exists": False}


    async def list_active_threads(self, limit: int = 100) -> List[str]:
        """
        List active conversation threads

        Args:
            limit: Maximum number of threads to return

        Returns:
            List of thread IDs
        """
        try:
            r = await self._get_redis()
            pattern = "chat:thread:*"

            # Scan for keys matching pattern
            thread_keys = []
            async for key in r.scan_iter(match=pattern, count=100):
                # Extract thread_id from key
                thread_id = key.replace("chat:thread:", "")
                thread_keys.append(thread_id)

                if len(thread_keys) >= limit:
                    break

            return thread_keys

        except Exception as e:
            print(f"[MemoryManager] Error listing active threads: {e}")
            return []


    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.aclose()

# Global memory manager instance
redis_manager = RedisManager()