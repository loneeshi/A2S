"""
Agent runner - per-agent execution loop.

Implements message processing, LLM calls, and tool execution following swarm-ide patterns.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from ..storage.repositories import AgentRepository, MessageRepository
from ..messaging.protocols import AgentMessage, MessageType, ToolCall, ToolResult
from ..messaging.tools import BUILTIN_TOOLS
from ..llm.client import LLMClient

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Per-agent execution loop.

    Processes messages using LLM with tool calls, similar to swarm-ide's AgentRunner:
    - Waits for wakeup events
    - Fetches unread messages
    - Runs LLM with tools
    - Executes tool calls (including send/create)
    - Updates llm_history
    """

    def __init__(
        self,
        agent_id: str,
        workspace_id: str,
        runtime: 'AgentRuntime',
        event_bus: 'AgentEventBus',
        llm_client: LLMClient
    ):
        """
        Initialize agent runner.

        Args:
            agent_id: Agent ID
            workspace_id: Workspace ID
            runtime: AgentRuntime instance
            event_bus: Event bus for events
            llm_client: LLM client
        """
        self.agent_id = agent_id
        self.workspace_id = workspace_id
        self.runtime = runtime
        self.event_bus = event_bus
        self.llm_client = llm_client

        self.wake_event = asyncio.Event()
        self.started = False
        self.running = False
        self.interrupt_requested = False

        # Repositories
        self.agent_repo = runtime.agent_repo
        self.message_repo = runtime.message_repo

    async def start(self):
        """Start the agent's event loop."""
        if self.started:
            return

        self.started = True
        asyncio.create_task(self._loop())

    async def wakeup(
        self,
        reason: str = "manual"
    ):
        """
        Trigger agent to process messages.

        Args:
            reason: Reason for wakeup
        """
        self.wake_event.set()
        await self.event_bus.emit(self.agent_id, {
            "event": "agent.wakeup",
            "data": {"agentId": self.agent_id, "reason": reason}
        })

    async def request_interrupt(self):
        """Request graceful interruption."""
        self.interrupt_requested = True
        self.wake_event.set()

    async def _loop(self):
        """Main event loop."""
        while True:
            await self.wake_event.wait()
            self.wake_event.clear()

            if self.running:
                continue

            self.running = True
            try:
                await self._process_until_idle()
            except Exception as e:
                logger.exception(f"Error in agent {self.agent_id}: {e}")
                await self.event_bus.emit(self.agent_id, {
                    "event": "agent.error",
                    "data": {"message": str(e)}
                })
            finally:
                self.running = False

    async def _process_until_idle(self):
        """Process all unread messages."""
        if self.interrupt_requested:
            self.interrupt_requested = False
            return

        # Get unread messages grouped by conversation
        unread_batches = await self.message_repo.list_unread_by_group(self.agent_id)

        if not unread_batches:
            return

        await self.event_bus.emit(self.agent_id, {
            "event": "agent.unread",
            "data": {
                "agentId": self.agent_id,
                "batches": len(unread_batches)
            }
        })

        # Process each group's messages
        for batch in unread_batches:
            if self.interrupt_requested:
                return

            await self._process_group_messages(
                batch['group_id'],
                batch['messages']
            )

    async def _process_group_messages(
        self,
        group_id: str,
        messages: List[Dict]
    ):
        """
        Process messages from a specific group.

        Args:
            group_id: Group ID
            messages: List of message dictionaries
        """
        # Load agent's current history
        agent = await self.agent_repo.get(self.agent_id)
        history = json.loads(agent['llm_history'])

        # Add messages to history
        for msg_dict in messages:
            msg = AgentMessage(**msg_dict)
            history.append(msg.to_history_format())

        # Mark messages as read
        last_msg_id = messages[-1]['id'] if messages else None
        if last_msg_id:
            await self.message_repo.mark_read(group_id, self.agent_id, last_msg_id)

        # Run LLM with tools (max 3 rounds of tool calls)
        max_rounds = 3
        for round_num in range(max_rounds):
            if self.interrupt_requested:
                return

            # Call LLM
            response = await self._call_llm(history, group_id, round_num)

            # Add assistant response to history
            assistant_msg = {
                "role": "assistant",
                "content": response.content
            }
            if response.tool_calls:
                assistant_msg["tool_calls"] = response.tool_calls

            history.append(assistant_msg)

            # Execute tool calls if any
            if not response.tool_calls:
                break

            for tool_call_dict in response.tool_calls:
                tool_call = ToolCall(
                    id=tool_call_dict.get("id", str(uuid.uuid4())),
                    name=tool_call_dict["function"]["name"],
                    arguments=json.loads(tool_call_dict["function"]["arguments"])
                )

                result = await self._execute_tool_call(tool_call, group_id)

                # Add tool result to history
                history.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name
                })

        # Save updated history
        await self.agent_repo.update_history(self.agent_id, json.dumps(history))

        await self.event_bus.emit(self.agent_id, {
            "event": "agent.done",
            "data": {"finishReason": "stop"}
        })

    async def _call_llm(
        self,
        history: List[Dict],
        group_id: str,
        round_num: int
    ) -> Any:
        """
        Call LLM with streaming support.

        Args:
            history: Conversation history
            group_id: Current group ID
            round_num: Round number

        Returns:
            LLM response with content and tool_calls
        """
        await self.event_bus.emit(self.agent_id, {
            "event": "agent.stream",
            "data": {"kind": "start", "round": round_num}
        })

        # Get available tools (builtin + agent-specific)
        agent = await self.agent_repo.get(self.agent_id)
        agent_tools = json.loads(agent.get('tools_json', '[]'))
        tools = BUILTIN_TOOLS + self._agent_tools_to_openai(agent_tools)

        # Call LLM (wrap sync call in async)
        response = await asyncio.to_thread(
            self.llm_client.chat,
            messages=history,
            tools=tools if tools else None,
            temperature=0.7
        )

        return response

    def _agent_tools_to_openai(self, agent_tools: List[str]) -> List[Dict]:
        """
        Convert agent tool list to OpenAI format.

        Args:
            agent_tools: List of tool names

        Returns:
            List of OpenAI tool definitions
        """
        # This would be defined based on benchmark tool specifications
        # For now, return empty
        return []

    async def _execute_tool_call(
        self,
        tool_call: ToolCall,
        group_id: str
    ) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool_call: Tool to execute
            group_id: Current group ID

        Returns:
            Tool result
        """
        await self.event_bus.emit(self.agent_id, {
            "event": "agent.stream",
            "data": {
                "kind": "tool_call_start",
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name
            }
        })

        try:
            # Check builtin tools first
            if tool_call.name in ["self", "list_agents", "create", "send",
                                  "list_groups", "create_group", "send_group_message"]:
                result = await self._execute_builtin_tool(tool_call, group_id)
            else:
                # Agent-specific tool (e.g., environment tool)
                result = await self._execute_agent_tool(tool_call)

            await self.event_bus.emit(self.agent_id, {
                "event": "agent.stream",
                "data": {
                    "kind": "tool_result",
                    "tool_call_id": tool_call.id,
                    "result": result
                }
            })

            return ToolResult(
                tool_call_id=tool_call.id,
                ok=True,
                result=result
            )

        except Exception as e:
            logger.exception(f"Tool execution error: {e}")
            return ToolResult(
                tool_call_id=tool_call.id,
                ok=False,
                result=None,
                error=str(e)
            )

    async def _execute_builtin_tool(
        self,
        tool_call: ToolCall,
        group_id: str
    ) -> Any:
        """
        Execute builtin agent tools.

        Args:
            tool_call: Tool call to execute
            group_id: Current group ID

        Returns:
            Tool result
        """
        tool_name = tool_call.name
        args = tool_call.arguments

        if tool_name == "self":
            agent = await self.agent_repo.get(self.agent_id)
            return {
                "ok": True,
                "agentId": self.agent_id,
                "workspaceId": self.workspace_id,
                "role": agent['role']
            }

        elif tool_name == "list_agents":
            agents = await self.agent_repo.list_by_workspace(self.workspace_id)
            return {
                "ok": True,
                "agents": [
                    {"id": a['id'], "role": a['role']}
                    for a in agents
                ]
            }

        elif tool_name == "create":
            # Create sub-agent
            role = args.get('role')
            guidance = args.get('guidance', '')

            new_agent_id = await self.runtime.create_sub_agent(
                workspace_id=self.workspace_id,
                role=role,
                parent_id=self.agent_id,
                guidance=guidance
            )

            # Create P2P group with new agent
            new_group_id = await self.runtime.group_repo.create_p2p(
                self.workspace_id, self.agent_id, new_agent_id
            )

            return {
                "ok": True,
                "agentId": new_agent_id,
                "groupId": new_group_id
            }

        elif tool_name == "send":
            # Send direct message
            to_agent_id = args.get('to')
            content = args.get('content')

            message_id = await self.runtime.send_message(
                sender_id=self.agent_id,
                target_id=to_agent_id,
                content=content,
                group_id=group_id
            )

            return {"ok": True, "messageId": message_id}

        elif tool_name == "list_groups":
            groups = await self.runtime.group_repo.list_by_agent(self.agent_id)
            return {
                "ok": True,
                "groups": [{"id": g['id'], "name": g['name']} for g in groups]
            }

        elif tool_name == "create_group":
            member_ids = args.get('memberIds', [])
            name = args.get('name', '')

            if self.agent_id not in member_ids:
                member_ids.append(self.agent_id)

            new_group_id = await self.runtime.group_repo.create(
                self.workspace_id, member_ids, name
            )

            return {"ok": True, "groupId": new_group_id}

        elif tool_name == "send_group_message":
            # Send group message
            target_group_id = args.get('groupId')
            content = args.get('content')

            # Verify membership
            members = await self.runtime.group_repo.list_members(target_group_id)
            if self.agent_id not in members:
                return {"ok": False, "error": "Not a member of this group"}

            # Create message
            message_id = str(uuid.uuid4())
            await self.message_repo.create(
                id=message_id,
                workspace_id=self.workspace_id,
                group_id=target_group_id,
                sender_id=self.agent_id,
                content_type=MessageType.TEXT,
                content=content
            )

            # Wake all members
            await self.runtime.wake_agents_for_group(target_group_id, self.agent_id)

            return {"ok": True, "messageId": message_id}

        else:
            return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    async def _execute_agent_tool(self, tool_call: ToolCall) -> Any:
        """
        Execute agent-specific tool (e.g., environment tool).

        Args:
            tool_call: Tool call to execute

        Returns:
            Tool result
        """
        # This would be implemented based on benchmark-specific tools
        # For now, return error
        return {
            "ok": False,
            "error": f"Agent-specific tool '{tool_call.name}' not implemented"
        }
