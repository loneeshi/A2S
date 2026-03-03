"""
Event bus for Agent communication and debugging.

Provides pub/sub mechanism for events like wakeup, stream, done, error.
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentEventBus:
    """
    Event bus for Agent runtime events.

    Implements pub/sub pattern for real-time event streaming.
    """

    def __init__(self, max_events_per_agent: int = 2000):
        """
        Initialize event bus.

        Args:
            max_events_per_agent: Maximum events to buffer per agent
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_buffers: Dict[str, List[Dict]] = defaultdict(list)
        self._max_events = max_events_per_agent
        self._lock = asyncio.Lock()

    def subscribe(
        self,
        agent_id: str,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Subscribe to events for a specific agent.

        Args:
            agent_id: Agent ID to subscribe to
            callback: Async callback function that receives event data
        """
        self._subscribers[agent_id].append(callback)
        logger.debug(f"New subscriber for agent {agent_id}")

    def unsubscribe(
        self,
        agent_id: str,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Unsubscribe from agent events.

        Args:
            agent_id: Agent ID
            callback: Callback to remove
        """
        if callback in self._subscribers[agent_id]:
            self._subscribers[agent_id].remove(callback)
            logger.debug(f"Removed subscriber for agent {agent_id}")

    async def emit(self, agent_id: str, event: Dict[str, Any]):
        """
        Emit an event for an agent.

        Args:
            agent_id: Agent ID
            event: Event data with "event" and "data" keys
        """
        # Add timestamp
        event["timestamp"] = datetime.utcnow().isoformat()

        # Buffer event
        async with self._lock:
            self._event_buffers[agent_id].append(event)

            # Trim buffer if too large
            if len(self._event_buffers[agent_id]) > self._max_events:
                self._event_buffers[agent_id] = self._event_buffers[agent_id][-self._max_events:]

        # Notify subscribers
        for callback in self._subscribers.get(agent_id, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in event callback for {agent_id}: {e}")

    def get_events(self, agent_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get buffered events for an agent.

        Args:
            agent_id: Agent ID
            limit: Optional limit on number of events

        Returns:
            List of event dictionaries
        """
        events = self._event_buffers.get(agent_id, [])
        if limit:
            return events[-limit:]
        return events

    async def clear_events(self, agent_id: str):
        """
        Clear event buffer for an agent.

        Args:
            agent_id: Agent ID
        """
        async with self._lock:
            if agent_id in self._event_buffers:
                del self._event_buffers[agent_id]

    def get_all_agent_ids(self) -> List[str]:
        """Get list of all agent IDs with events."""
        return list(self._event_buffers.keys())


class EventLogger:
    """
    Logs events to database for persistence and replay.
    """

    def __init__(self, db_path: str):
        """
        Initialize event logger.

        Args:
            db_path: Path to database
        """
        from ..storage.database import DatabaseManager
        self.db = DatabaseManager(db_path)

    async def log_event(
        self,
        agent_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """
        Log an event to database.

        Args:
            agent_id: Agent ID
            event_type: Event type ("wakeup" | "stream" | "done" | "error")
            event_data: Event data as dictionary
        """
        await self.db.execute(
            """
            INSERT INTO agent_events (agent_id, event_type, event_data, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (
                agent_id,
                event_type,
                json.dumps(event_data),
                datetime.utcnow().isoformat()
            )
        )
        await self.db.commit()

    async def get_events(
        self,
        agent_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve events from database.

        Args:
            agent_id: Agent ID
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        if event_type:
            async with await self.db.execute(
                """
                SELECT * FROM agent_events
                WHERE agent_id = ? AND event_type = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (agent_id, event_type, limit)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with await self.db.execute(
                """
                SELECT * FROM agent_events
                WHERE agent_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (agent_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            {
                "id": row[0],
                "agent_id": row[1],
                "event_type": row[2],
                "event_data": json.loads(row[3]) if row[3] else {},
                "timestamp": row[4]
            }
            for row in rows
        ]
