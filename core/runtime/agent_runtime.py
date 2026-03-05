"""
Agent runtime for managing multi-agent collaboration.

Implements swarm-ide patterns: message passing, independent histories, event-driven coordination.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from ..storage.repositories import (
    AgentRepository,
    MessageRepository,
    GroupRepository,
)
from ..messaging.protocols import AgentMessage, MessageType
from ..messaging.tools import BUILTIN_TOOLS
from ..llm.client import LLMClient
from .event_bus import AgentEventBus

logger = logging.getLogger(__name__)


class AgentRuntime:
    """
    Main runtime managing all agents in a workspace.

    Similar to swarm-ide's AgentRuntime:
    - Manages AgentRunner instances per agent
    - Handles wakeup events
    - Coordinates message passing
    - Maintains event bus for streaming
    """

    def __init__(
        self, workspace_id: str, db_path: str, llm_client: Optional[LLMClient] = None
    ):
        """
        Initialize runtime.

        Args:
            workspace_id: Workspace identifier
            db_path: Path to SQLite database
            llm_client: Optional LLM client (defaults to new instance)
        """
        self.workspace_id = workspace_id
        self.db_path = db_path
        self.runners: Dict[str, "AgentRunner"] = {}
        self.event_bus = AgentEventBus()
        self.llm_client = llm_client or LLMClient()

        # Repositories
        self.agent_repo = AgentRepository(db_path)
        self.message_repo = MessageRepository(db_path)
        self.group_repo = GroupRepository(db_path)

        self._bootstrapped = False

    async def bootstrap(self):
        """Bootstrap runtime by loading existing agents."""
        if self._bootstrapped:
            return

        self._bootstrapped = True

        # Load all non-human agents
        agents = await self.agent_repo.list_by_workspace(self.workspace_id)
        for agent in agents:
            if agent["role"] != "human":
                self.ensure_runner(agent["id"])

        logger.info(f"Bootstrapped runtime with {len(self.runners)} agents")

    def ensure_runner(self, agent_id: str) -> "AgentRunner":
        """
        Get or create AgentRunner for agent.

        Args:
            agent_id: Agent ID

        Returns:
            AgentRunner instance
        """
        if agent_id in self.runners:
            return self.runners[agent_id]

        # Import here to avoid circular dependency
        from .agent_runner import AgentRunner

        runner = AgentRunner(
            agent_id=agent_id,
            workspace_id=self.workspace_id,
            runtime=self,
            event_bus=self.event_bus,
            llm_client=self.llm_client,
        )
        self.runners[agent_id] = runner
        asyncio.create_task(runner.start())
        return runner

    async def wake_agent(
        self,
        agent_id: str,
        reason: Literal["direct_message", "group_message", "manual"] = "manual",
    ):
        """
        Wake up an agent to process messages.

        Args:
            agent_id: Agent to wake
            reason: Reason for wakeup
        """
        await self.bootstrap()

        # Check if agent exists and is not human
        agent = await self.agent_repo.get(agent_id)
        if not agent or agent["role"] == "human":
            return

        runner = self.ensure_runner(agent_id)
        await runner.wakeup(reason)

    async def wake_agents_for_group(self, group_id: str, sender_id: str):
        """
        Wake all agents in a group except sender.

        Args:
            group_id: Group ID
            sender_id: Sender agent ID (to exclude)
        """
        await self.bootstrap()

        members = await self.group_repo.list_members(group_id)
        for member_id in members:
            if member_id == sender_id:
                continue

            agent = await self.agent_repo.get(member_id)
            if agent and agent["role"] != "human":
                await self.wake_agent(member_id, "group_message")

    async def interrupt_all(self):
        """Interrupt all running agents."""
        for runner in self.runners.values():
            await runner.request_interrupt()

    async def wait_for_idle(self, timeout: float = 30.0) -> bool:
        """
        Wait for all agents to become idle.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all agents idle, False if timeout
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check if any runner is active
            any_active = any(runner.running for runner in self.runners.values())

            if not any_active:
                return True

            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning("Timeout waiting for agents to idle")
                return False

            await asyncio.sleep(0.1)

    async def create_sub_agent(
        self,
        workspace_id: str,
        role: str,
        parent_id: str,
        guidance: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> str:
        """
        Create a sub-agent.

        Args:
            workspace_id: Workspace ID
            role: Agent role
            parent_id: Parent agent ID
            guidance: Optional guidance/prompt
            domain: Optional domain

        Returns:
            New agent ID
        """
        agent_id = str(uuid.uuid4())

        # Build initial history with system prompt (cache-aware + working context)
        from ..prompts.prompt_builder import CacheOptimizedPromptBuilder
        from ..memory.manager import get_memory_manager

        prompt_builder = CacheOptimizedPromptBuilder(domain or "general")

        working_ctx = None
        try:
            memory_mgr = get_memory_manager()
            working_ctx = memory_mgr.get_working_context(
                agent_name=parent_id,
                domain=domain or "general",
                task_type=role,
            )
        except Exception:
            pass

        system_prompt = prompt_builder.build_prompt(
            role=role,
            task_context={},
            include_examples=False,
            working_context=working_ctx,
        )

        guidance_text = f"\n\nAdditional instructions:\n{guidance}" if guidance else ""

        initial_history = [
            {
                "role": "system",
                "content": f"""你是一个多 Agent 系统中的 Agent。

agent_id: {agent_id}
workspace_id: {workspace_id}
role: {role}
parent_id: {parent_id}

{system_prompt}{guidance_text}

使用以下工具与其他 Agent 通信：
- list_agents(): 查看所有 Agent
- create(role, guidance): 创建子 Agent
- send(to, content): 发送直接消息
- send_group_message(groupId, content): 发送群组消息
""",
            }
        ]

        # Create agent in database
        await self.agent_repo.create(
            id=agent_id,
            workspace_id=workspace_id,
            role=role,
            parent_id=parent_id,
            domain=domain,
            llm_history=json.dumps(initial_history),
            tools_json=json.dumps([]),
            metadata=json.dumps({"created_by": parent_id}),
        )

        logger.info(f"Created sub-agent: {agent_id} (role={role}, parent={parent_id})")

        return agent_id

    async def send_message(
        self,
        sender_id: str,
        target_id: str,
        content: str,
        group_id: Optional[str] = None,
    ) -> str:
        """
        Send a message from one agent to another.

        Args:
            sender_id: Sender agent ID
            target_id: Target agent ID
            content: Message content
            group_id: Optional group ID (creates P2P if not provided)

        Returns:
            Message ID
        """
        # Create P2P group if not provided
        if not group_id:
            group_id = await self.group_repo.create_p2p(
                self.workspace_id, sender_id, target_id
            )

        # Create message
        message_id = str(uuid.uuid4())
        await self.message_repo.create(
            id=message_id,
            workspace_id=self.workspace_id,
            group_id=group_id,
            sender_id=sender_id,
            content_type=MessageType.TEXT,
            content=content,
        )

        # Wake target agent
        await self.wake_agent(target_id, "direct_message")

        logger.debug(f"Sent message: {message_id} from {sender_id} to {target_id}")

        return message_id

    async def create_and_send(
        self, sender_id: str, target_id: str, message: str
    ) -> str:
        """
        Create a P2P group and send a message.

        Convenience method for direct agent communication.

        Args:
            sender_id: Sender agent ID
            target_id: Target agent ID
            message: Message content

        Returns:
            Message ID
        """
        return await self.send_message(sender_id, target_id, message)

    @property
    def extension_registry(self):
        """
        Get the extension registry for registering hooks and submitting proposals.

        Returns:
            ExtensionRegistry singleton
        """
        from ..optimizer.extension_hooks import get_extension_registry

        return get_extension_registry()
