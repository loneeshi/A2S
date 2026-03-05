"""
SPEC_v1.0 Swarm-IDE Event Bridge (Python Core)

Bridges Python agent lifecycle events to the Next.js Swarm-IDE visualization layer.
Events are emitted via STDOUT using the "EVENT:" protocol, picked up by
PythonAgentManager (python-manager.ts), and relayed to the WorkspaceUIBus SSE stream.

Event types match the Swarm-IDE UIEvent schema (ui-bus.ts) exactly:
  - ui.agent.created        → New agent node discovered in tree
  - ui.agent.llm.start      → Agent starts reasoning (pulse-glow in UI)
  - ui.agent.llm.done       → Agent finishes reasoning
  - ui.agent.tool_call.start → Tool execution begins
  - ui.agent.tool_call.done  → Tool execution completes
  - ui.agent.handoff         → Task handoff between agents (Liquid Flow animation)
  - ui.agent.history.persisted → History snapshot saved
  - ui.message.created       → New message in a group
  - ui.log.stream            → Console log entry (reasoning/content/tool deltas)
  - ui.cache.metrics         → Prompt cache performance metrics (custom extension)
"""

import json
import sys
import time
import uuid
from typing import Any, Dict, List, Optional


class UIBridge:
    """
    Stateful event bridge from Python agent runtime to Swarm-IDE frontend.

    Usage:
        bridge = UIBridge(workspace_id="ws-123")
        bridge.agent_created(agent_id="a1", role="NavigationWorker")
        bridge.llm_start(agent_id="a1", group_id="g1", round_num=0)
        bridge.log(agent_id="a1", kind="reasoning", message="I should go to...")
        bridge.llm_done(agent_id="a1", group_id="g1", round_num=0)

    Legacy static API is preserved for backward compatibility.
    """

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id

    def _emit(self, event_type: str, data: dict):
        payload = {"event": event_type, "data": data, "timestamp": time.time()}
        line = f"EVENT:{json.dumps(payload, ensure_ascii=False)}"
        print(line, flush=True)

    # ── Agent lifecycle ─────────────────────────────────────────

    def agent_created(self, agent_id: str, role: str, parent_id: Optional[str] = None):
        """New agent node discovered. Triggers tree layout update in UI."""
        self._emit(
            "ui.agent.created",
            {
                "workspaceId": self.workspace_id,
                "agent": {"id": agent_id, "role": role, "parentId": parent_id},
            },
        )

    # ── LLM lifecycle ───────────────────────────────────────────

    def llm_start(self, agent_id: str, group_id: str, round_num: int = 0):
        """Agent starts LLM reasoning. Triggers pulse-glow animation in UI."""
        self._emit(
            "ui.agent.llm.start",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "groupId": group_id,
                "round": round_num,
            },
        )

    def llm_done(
        self,
        agent_id: str,
        group_id: str,
        round_num: int = 0,
        finish_reason: Optional[str] = "stop",
    ):
        """Agent finishes LLM reasoning."""
        self._emit(
            "ui.agent.llm.done",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "groupId": group_id,
                "round": round_num,
                "finishReason": finish_reason,
            },
        )

    # ── Tool calls ──────────────────────────────────────────────

    def tool_call_start(
        self,
        agent_id: str,
        group_id: str,
        tool_name: str,
        tool_call_id: Optional[str] = None,
    ):
        """Tool execution begins."""
        self._emit(
            "ui.agent.tool_call.start",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "groupId": group_id,
                "toolCallId": tool_call_id or str(uuid.uuid4())[:8],
                "toolName": tool_name,
            },
        )

    def tool_call_done(
        self,
        agent_id: str,
        group_id: str,
        tool_name: str,
        ok: bool = True,
        tool_call_id: Optional[str] = None,
    ):
        """Tool execution completes."""
        self._emit(
            "ui.agent.tool_call.done",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "groupId": group_id,
                "toolCallId": tool_call_id or str(uuid.uuid4())[:8],
                "toolName": tool_name,
                "ok": ok,
            },
        )

    # ── Handoff (Liquid Flow) ───────────────────────────────────

    def handoff(
        self,
        source_id: str,
        target_id: str,
        context_size: int = 1,
        payload_summary: Optional[str] = None,
    ):
        """
        Task handoff between agents.
        Triggers the "Liquid Flow" particle animation in the UI topology canvas.
        """
        self._emit(
            "ui.agent.handoff",
            {
                "workspaceId": self.workspace_id,
                "source": source_id,
                "target": target_id,
                "contextSize": context_size,
                "isAnimating": True,
                "payloadSummary": payload_summary,
            },
        )

    # ── Messages ────────────────────────────────────────────────

    def message_created(
        self,
        group_id: str,
        sender_id: str,
        message_id: Optional[str] = None,
        member_ids: Optional[List[str]] = None,
    ):
        """New message in a group conversation."""
        self._emit(
            "ui.message.created",
            {
                "workspaceId": self.workspace_id,
                "groupId": group_id,
                "memberIds": member_ids or [],
                "message": {
                    "id": message_id or str(uuid.uuid4()),
                    "senderId": sender_id,
                    "sendTime": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                },
            },
        )

    # ── History persistence ─────────────────────────────────────

    def history_persisted(self, agent_id: str, group_id: str, history_length: int):
        """Agent history snapshot saved."""
        self._emit(
            "ui.agent.history.persisted",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "groupId": group_id,
                "historyLength": history_length,
            },
        )

    # ── Console log stream ──────────────────────────────────────

    def log(self, agent_id: str, kind: str, message: str):
        """
        Stream a log entry to the Execution Console in the UI.

        Kinds: reasoning, content, tool_call, tool_result, system, error
        """
        self._emit(
            "ui.log.stream",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "kind": kind,
                "message": message,
            },
        )

    # ── Prompt Cache Metrics (custom extension) ─────────────────

    def cache_metrics(
        self,
        agent_id: str,
        hit_rate: float,
        hit_tokens: int,
        total_tokens: int,
        status: str = "partial",
        cache_hit_position: int = 0,
        cost_saved_usd: float = 0.0,
    ):
        """
        Prompt cache performance metrics for the Cache Heatmap sidebar.

        Args:
            agent_id: Agent that made the LLM call
            hit_rate: Cache hit percentage (0.0 - 1.0)
            hit_tokens: Number of tokens served from cache
            total_tokens: Total prompt tokens
            status: "hit" | "partial" | "miss"
            cache_hit_position: Token index where cache hit begins
            cost_saved_usd: Estimated cost savings
        """
        self._emit(
            "ui.cache.metrics",
            {
                "workspaceId": self.workspace_id,
                "agentId": agent_id,
                "hitRate": hit_rate,
                "hitTokens": hit_tokens,
                "totalTokens": total_tokens,
                "status": status,
                "cacheHitPosition": cache_hit_position,
                "costSavedUsd": cost_saved_usd,
            },
        )

    # ── DB write notification ───────────────────────────────────

    def db_write(
        self, table: str, action: str = "insert", record_id: Optional[str] = None
    ):
        """Database write event for UI reactivity."""
        self._emit(
            "ui.db.write",
            {
                "workspaceId": self.workspace_id,
                "table": table,
                "action": action,
                "recordId": record_id,
            },
        )

    # ── Static legacy API (backward compat) ─────────────────────

    @staticmethod
    def _static_emit(event_type: str, data: dict):
        payload = {"event": event_type, "data": data, "timestamp": time.time()}
        print(f"EVENT:{json.dumps(payload, ensure_ascii=False)}", flush=True)

    @classmethod
    def emit_agent_update(
        cls,
        agent_id: str,
        role: Optional[str] = None,
        status: str = "idle",
        tokens: int = 0,
        latency: int = 0,
    ):
        data = {
            "id": agent_id,
            "role": role,
            "status": status,
            "total_tokens_used": tokens,
            "llm_latency_ms": latency,
        }
        cls._static_emit("ui.agent.update", data)

    @classmethod
    def emit_handoff(
        cls,
        source_id: str,
        target_id: str,
        payload_size: int = 1,
        is_animating: bool = True,
    ):
        data = {
            "source": source_id,
            "target": target_id,
            "context_size": payload_size,
            "isAnimating": is_animating,
        }
        cls._static_emit("ui.agent.handoff", data)

    @classmethod
    def emit_log(cls, agent_id: str, kind: str, message: str):
        data = {"agentId": agent_id, "kind": kind, "message": message}
        cls._static_emit("ui.log.stream", data)
