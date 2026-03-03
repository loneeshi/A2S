"""
Data access layer for Agent runtime.

Provides repository pattern for accessing agents, messages, groups, and workspaces.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class WorkspaceRepository:
    """Repository for workspace operations."""

    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)

    async def create(
        self,
        workspace_id: str,
        name: str,
        benchmark_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new workspace.

        Args:
            workspace_id: Unique workspace identifier
            name: Workspace name
            benchmark_name: Associated benchmark name

        Returns:
            Created workspace record
        """
        await self.db.execute(
            """
            INSERT INTO workspaces (id, name, benchmark_name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (workspace_id, name, benchmark_name, datetime.utcnow().isoformat())
        )
        await self.db.commit()

        return {
            "id": workspace_id,
            "name": name,
            "benchmark_name": benchmark_name,
            "created_at": datetime.utcnow().isoformat()
        }

    async def get(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get workspace by ID."""
        async with await self.db.execute(
            "SELECT * FROM workspaces WHERE id = ?",
            (workspace_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "benchmark_name": row[2],
                    "created_at": row[3]
                }
        return None

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all workspaces."""
        async with await self.db.execute(
            "SELECT * FROM workspaces ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "benchmark_name": row[2],
                    "created_at": row[3]
                }
                for row in rows
            ]


class AgentRepository:
    """Repository for agent operations."""

    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)

    async def create(
        self,
        id: str,
        workspace_id: str,
        role: str,
        llm_history: str,
        domain: Optional[str] = None,
        parent_id: Optional[str] = None,
        tools_json: Optional[str] = None,
        metadata: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new agent.

        Args:
            id: Unique agent identifier
            workspace_id: Workspace ID
            role: Agent role ("manager" | "worker" | "human")
            llm_history: JSON string of LLM conversation history
            domain: Optional domain identifier
            parent_id: Optional parent agent ID
            tools_json: Optional JSON string of tool names
            metadata: Optional JSON string of metadata

        Returns:
            Created agent record
        """
        await self.db.execute(
            """
            INSERT INTO agents (id, workspace_id, role, parent_id, domain, tools_json, llm_history, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id, workspace_id, role, parent_id, domain,
                tools_json or "[]", llm_history,
                metadata or "{}", datetime.utcnow().isoformat()
            )
        )
        await self.db.commit()

        logger.info(f"Created agent: {id} (role={role}, workspace={workspace_id})")

        return await self.get(id)

    async def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID."""
        async with await self.db.execute(
            "SELECT * FROM agents WHERE id = ?",
            (agent_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "workspace_id": row[1],
                    "role": row[2],
                    "parent_id": row[3],
                    "domain": row[4],
                    "tools_json": row[5],
                    "llm_history": row[6],
                    "metadata": row[7],
                    "status": row[8],
                    "created_at": row[9]
                }
        return None

    async def update_history(self, agent_id: str, llm_history: str):
        """Update agent's LLM history."""
        await self.db.execute(
            "UPDATE agents SET llm_history = ? WHERE id = ?",
            (llm_history, agent_id)
        )
        await self.db.commit()

    async def update_status(self, agent_id: str, status: str):
        """Update agent status."""
        await self.db.execute(
            "UPDATE agents SET status = ? WHERE id = ?",
            (status, agent_id)
        )
        await self.db.commit()

    async def list_by_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """List all agents in a workspace."""
        async with await self.db.execute(
            "SELECT * FROM agents WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "workspace_id": row[1],
                    "role": row[2],
                    "parent_id": row[3],
                    "domain": row[4],
                    "tools_json": row[5],
                    "llm_history": row[6],
                    "metadata": row[7],
                    "status": row[8],
                    "created_at": row[9]
                }
                for row in rows
            ]

    async def list_children(self, parent_id: str) -> List[Dict[str, Any]]:
        """List child agents of a given agent."""
        async with await self.db.execute(
            "SELECT * FROM agents WHERE parent_id = ? ORDER BY created_at",
            (parent_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "workspace_id": row[1],
                    "role": row[2],
                    "parent_id": row[3],
                    "domain": row[4],
                    "tools_json": row[5],
                    "llm_history": row[6],
                    "metadata": row[7],
                    "status": row[8],
                    "created_at": row[9]
                }
                for row in rows
            ]


class GroupRepository:
    """Repository for group operations."""

    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)

    async def create(
        self,
        workspace_id: str,
        member_ids: List[str],
        name: Optional[str] = None
    ) -> str:
        """
        Create a new group.

        Args:
            workspace_id: Workspace ID
            member_ids: List of agent IDs to add to group
            name: Optional group name

        Returns:
            Group ID
        """
        group_id = str(uuid.uuid4())

        # Create group
        await self.db.execute(
            """
            INSERT INTO groups (id, workspace_id, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (group_id, workspace_id, name, datetime.utcnow().isoformat())
        )

        # Add members
        now = datetime.utcnow().isoformat()
        await self.db.executemany(
            """
            INSERT INTO group_members (group_id, agent_id, joined_at)
            VALUES (?, ?, ?)
            """,
            [(group_id, agent_id, now) for agent_id in member_ids]
        )

        await self.db.commit()

        logger.info(f"Created group: {group_id} with {len(member_ids)} members")

        return group_id

    async def create_p2p(
        self,
        workspace_id: str,
        agent1_id: str,
        agent2_id: str
    ) -> str:
        """
        Create a point-to-point group between two agents.

        Args:
            workspace_id: Workspace ID
            agent1_id: First agent ID
            agent2_id: Second agent ID

        Returns:
            Group ID
        """
        return await self.create(workspace_id, [agent1_id, agent2_id], name="p2p")

    async def get(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get group by ID."""
        async with await self.db.execute(
            "SELECT * FROM groups WHERE id = ?",
            (group_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "workspace_id": row[1],
                    "name": row[2],
                    "context_tokens": row[3],
                    "created_at": row[4]
                }
        return None

    async def list_members(self, group_id: str) -> List[str]:
        """List member IDs in a group."""
        async with await self.db.execute(
            "SELECT agent_id FROM group_members WHERE group_id = ?",
            (group_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def list_by_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """List groups that an agent is a member of."""
        async with await self.db.execute(
            """
            SELECT g.* FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            WHERE gm.agent_id = ?
            ORDER BY g.created_at DESC
            """,
            (agent_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "workspace_id": row[1],
                    "name": row[2],
                    "context_tokens": row[3],
                    "created_at": row[4]
                }
                for row in rows
            ]

    async def get_last_read_message_id(self, group_id: str, agent_id: str) -> Optional[str]:
        """Get the last read message ID for an agent in a group."""
        async with await self.db.execute(
            "SELECT last_read_message_id FROM group_members WHERE group_id = ? AND agent_id = ?",
            (group_id, agent_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


class MessageRepository:
    """Repository for message operations."""

    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)

    async def create(
        self,
        id: str,
        workspace_id: str,
        group_id: str,
        sender_id: str,
        content_type: str,
        content: str,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new message.

        Args:
            id: Message ID
            workspace_id: Workspace ID
            group_id: Group ID
            sender_id: Sender agent ID
            content_type: Content type ("text" | "tool_call" | "tool_result")
            content: Message content
            tool_call_id: Optional tool call ID
            tool_name: Optional tool name

        Returns:
            Created message record
        """
        await self.db.execute(
            """
            INSERT INTO messages (id, workspace_id, group_id, sender_id, content_type, content, send_time, tool_call_id, tool_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id, workspace_id, group_id, sender_id, content_type,
                content, datetime.utcnow().isoformat(), tool_call_id, tool_name
            )
        )
        await self.db.commit()

        logger.debug(f"Created message: {id} (group={group_id}, sender={sender_id})")

        return await self.get(id)

    async def get(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message by ID."""
        async with await self.db.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "workspace_id": row[1],
                    "group_id": row[2],
                    "sender_id": row[3],
                    "content_type": row[4],
                    "content": row[5],
                    "send_time": row[6],
                    "tool_call_id": row[7],
                    "tool_name": row[8]
                }
        return None

    async def list_unread_by_group(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        List unread messages for an agent, grouped by conversation (group).

        Returns:
            List of {group_id, messages} dicts
        """
        # Get all groups the agent is in
        group_repo = GroupRepository(self.db.db_path)
        groups = await group_repo.list_by_agent(agent_id)

        unread_batches = []

        for group in groups:
            group_id = group["id"]

            # Get last read message ID for this group
            last_read_id = await group_repo.get_last_read_message_id(group_id, agent_id)

            # Query unread messages
            if last_read_id:
                # Get messages sent after last read
                async with await self.db.execute(
                    """
                    SELECT * FROM messages
                    WHERE group_id = ? AND id > ?
                    ORDER BY send_time ASC
                    """,
                    (group_id, last_read_id)
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                # Get all messages for this group
                async with await self.db.execute(
                    """
                    SELECT * FROM messages
                    WHERE group_id = ?
                    ORDER BY send_time ASC
                    """,
                    (group_id,)
                ) as cursor:
                    rows = await cursor.fetchall()

            if rows:
                messages = [
                    {
                        "id": row[0],
                        "workspace_id": row[1],
                        "group_id": row[2],
                        "sender_id": row[3],
                        "content_type": row[4],
                        "content": row[5],
                        "send_time": row[6],
                        "tool_call_id": row[7],
                        "tool_name": row[8]
                    }
                    for row in rows
                ]
                unread_batches.append({
                    "group_id": group_id,
                    "messages": messages
                })

        return unread_batches

    async def mark_read(self, group_id: str, agent_id: str, message_id: str):
        """Mark a message as read by updating the agent's last read pointer."""
        await self.db.execute(
            """
            UPDATE group_members
            SET last_read_message_id = ?
            WHERE group_id = ? AND agent_id = ?
            """,
            (message_id, group_id, agent_id)
        )
        await self.db.commit()

    async def list_by_group(self, group_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent messages in a group."""
        async with await self.db.execute(
            """
            SELECT * FROM messages
            WHERE group_id = ?
            ORDER BY send_time DESC
            LIMIT ?
            """,
            (group_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "workspace_id": row[1],
                    "group_id": row[2],
                    "sender_id": row[3],
                    "content_type": row[4],
                    "content": row[5],
                    "send_time": row[6],
                    "tool_call_id": row[7],
                    "tool_name": row[8]
                }
                for row in reversed(rows)  # Return in chronological order
            ]
