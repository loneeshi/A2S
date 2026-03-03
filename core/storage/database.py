"""
Database connection and schema management for Agent runtime.

Uses aiosqlite for async SQLite operations with proper schema initialization.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Async SQLite database manager.

    Handles connection lifecycle and schema initialization.
    """

    def __init__(self, db_path: str):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).resolve()
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> aiosqlite.Connection:
        """
        Get or create database connection.

        Returns:
            Active aiosqlite connection
        """
        async with self._lock:
            if self._conn is None:
                # Ensure parent directory exists
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

                self._conn = await aiosqlite.connect(self.db_path)
                await self._init_schema()

                # Enable WAL mode for better concurrency
                await self._conn.execute("PRAGMA journal_mode=WAL")
                await self._conn.execute("PRAGMA synchronous=NORMAL")

                logger.info(f"Connected to database: {self.db_path}")

            return self._conn

    async def _init_schema(self):
        """Initialize database tables."""
        if self._conn is None:
            raise RuntimeError("Database not connected")

        # Workspaces table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                benchmark_name TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Agents table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                role TEXT NOT NULL,
                parent_id TEXT,
                domain TEXT,
                tools_json TEXT,
                llm_history TEXT NOT NULL,
                metadata TEXT,
                status TEXT DEFAULT 'idle',
                created_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (parent_id) REFERENCES agents(id)
            )
        """)

        # Groups table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT,
                context_tokens INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            )
        """)

        # Group members table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                last_read_message_id TEXT,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (group_id, agent_id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Messages table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                send_time TEXT NOT NULL,
                tool_call_id TEXT,
                tool_name TEXT,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (group_id) REFERENCES groups(id),
                FOREIGN KEY (sender_id) REFERENCES agents(id)
            )
        """)

        # Agent events table
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)

        # Create indexes for performance
        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_agents_workspace
            ON agents(workspace_id)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_group
            ON messages(group_id, send_time)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_members_agent
            ON group_members(agent_id)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_unread
            ON messages(group_id, send_time)
        """)

        await self._conn.commit()
        logger.info("Database schema initialized")

    async def close(self):
        """Close database connection."""
        async with self._lock:
            if self._conn:
                await self._conn.close()
                self._conn = None
                logger.info("Database connection closed")

    async def execute(self, sql: str, params: tuple = ()):
        """
        Execute a SQL query.

        Args:
            sql: SQL query
            params: Query parameters

        Returns:
            Cursor
        """
        conn = await self.connect()
        return await conn.execute(sql, params)

    async def executemany(self, sql: str, params_list: list):
        """
        Execute a SQL query multiple times.

        Args:
            sql: SQL query
            params_list: List of parameter tuples

        Returns:
            Cursor
        """
        conn = await self.connect()
        return await conn.executemany(sql, params_list)

    async def commit(self):
        """Commit pending transactions."""
        if self._conn:
            await self._conn.commit()

    async def rollback(self):
        """Rollback pending transactions."""
        if self._conn:
            await self._conn.rollback()
