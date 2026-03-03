"""
Agent Execution Tracing Manager

追踪管理器，负责在 Agent 执行过程中自动收集和记录追踪数据。
"""

from __future__ import annotations
import asyncio
import uuid
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime
from pathlib import Path
import json
from contextlib import asynccontextmanager

from .schema import (
    TaskTrace, AgentNodeState, TraceEvent, EventType,
    NodeType, NodeStatus, create_trace_event, create_agent_node, create_task_trace,
    LLMApiCallTrace, ToolCallRecord, HandoffVector,
    PromptCachingInfo, CacheStatus, DynamicMemory, ReflectionTrace, BenchmarkContext
)


class TracingManager:
    """
    追踪管理器

    负责管理整个任务执行过程的追踪数据收集。
    """

    def __init__(
        self,
        task_name: str,
        task_description: str,
        output_dir: Optional[str] = None,
        auto_save: bool = True,
        save_interval: int = 10  # 每N个事件自动保存一次
    ):
        self.task_trace = create_task_trace(task_name, task_description)
        self.output_dir = Path(output_dir) if output_dir else None
        self.auto_save = auto_save
        self.save_interval = save_interval
        self._event_count = 0
        self._lock = asyncio.Lock()

    # ===== Node Management =====

    async def create_node(
        self,
        node_type: NodeType,
        role: str,
        system_prompt: str,
        user_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        parent_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """创建新的 Agent 节点"""
        depth = 0
        if parent_id:
            parent_node = self.task_trace.get_node(parent_id)
            if parent_node:
                depth = parent_node.depth + 1
                parent_node.child_ids.append(node_id)  # 会在创建后更新

        node = create_agent_node(
            node_type=node_type,
            role=role,
            system_prompt=system_prompt,
            user_messages=user_messages,
            tools=tools,
            parent_id=parent_id,
            depth=depth,
            **kwargs
        )

        # 更新父节点的 child_ids
        if parent_id:
            parent_node = self.task_trace.get_node(parent_id)
            if parent_node and node.node_id not in parent_node.child_ids:
                parent_node.child_ids.append(node.node_id)

        self.task_trace.add_node(node)

        # 记录节点创建事件
        await self.record_event(
            create_trace_event(
                event_type=EventType.NODE_CREATED,
                node_id=node.node_id,
                content={
                    "role": role,
                    "depth": depth,
                    "parent_id": parent_id
                }
            )
        )

        return node.node_id

    async def start_node(self, node_id: str) -> None:
        """标记节点开始执行"""
        node = self.task_trace.get_node(node_id)
        if node:
            node.status = NodeStatus.RUNNING
            node.started_at = datetime.utcnow()

            await self.record_event(
                create_trace_event(
                    event_type=EventType.NODE_STARTED,
                    node_id=node_id
                )
            )

    async def complete_node(self, node_id: str, success: bool = True) -> None:
        """标记节点完成"""
        node = self.task_trace.get_node(node_id)
        if node:
            node.status = NodeStatus.COMPLETED if success else NodeStatus.FAILED
            node.completed_at = datetime.utcnow()
            node.total_execution_time_ms = (
                node.completed_at - node.started_at
            ).total_seconds() * 1000 if node.started_at else 0.0

            await self.record_event(
                create_trace_event(
                    event_type=EventType.NODE_COMPLETED if success else EventType.NODE_FAILED,
                    node_id=node_id
                )
            )

    # ===== Event Recording =====

    async def record_event(self, event: TraceEvent) -> None:
        """记录事件"""
        async with self._lock:
            self.task_trace.add_event(event)
            self._event_count += 1

            # 自动保存
            if self.auto_save and self._event_count % self.save_interval == 0:
                await self.save()

    async def record_llm_call(
        self,
        node_id: str,
        model: str,
        messages: List[Dict[str, Any]],
        response_content: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: float,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        cache_info: Optional[PromptCachingInfo] = None,
        **kwargs
    ) -> str:
        """记录 LLM 调用"""
        call_id = str(uuid.uuid4())

        # 记录开始事件
        await self.record_event(
            create_trace_event(
                event_type=EventType.LLM_CALL_START,
                node_id=node_id,
                content={"model": model, "call_id": call_id}
            )
        )

        # 创建 LLM 调用追踪
        llm_trace = LLMApiCallTrace(
            call_id=call_id,
            timestamp=datetime.utcnow(),
            model=model,
            messages=messages,
            tools=tools,
            response_content=response_content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cache_info=cache_info,
            latency_ms=latency_ms,
            **kwargs
        )

        # 记录完成事件
        await self.record_event(
            create_trace_event(
                event_type=EventType.LLM_CALL_COMPLETE,
                node_id=node_id,
                content={
                    "call_id": call_id,
                    "model": model,
                    "total_tokens": total_tokens,
                    "latency_ms": latency_ms
                },
                llm_call_trace=llm_trace
            )
        )

        # 更新节点统计
        node = self.task_trace.get_node(node_id)
        if node:
            node.llm_call_count += 1
            node.total_tokens_used += total_tokens

        return call_id

    async def record_tool_call(
        self,
        node_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
        **kwargs
    ) -> str:
        """记录工具调用"""
        call_id = str(uuid.uuid4())

        # 创建工具调用记录
        tool_record = ToolCallRecord(
            call_id=call_id,
            tool_name=tool_name,
            arguments=arguments,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            status="success" if not error else "error",
            result=result,
            error_message=error,
            execution_time_ms=execution_time_ms,
            **kwargs
        )

        # 记录事件
        event_type = EventType.TOOL_CALL_COMPLETE
        await self.record_event(
            create_trace_event(
                event_type=event_type,
                node_id=node_id,
                content={
                    "tool_name": tool_name,
                    "success": not error
                },
                tool_call_record=tool_record
            )
        )

        # 更新节点统计
        node = self.task_trace.get_node(node_id)
        if node:
            node.tool_call_count += 1

        return call_id

    async def record_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        to_agent_role: str,
        message_content: str,
        **kwargs
    ) -> str:
        """记录任务移交"""
        handoff_id = str(uuid.uuid4())

        handoff = HandoffVector(
            handoff_id=handoff_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            to_agent_role=to_agent_role,
            timestamp=datetime.utcnow(),
            message_content=message_content,
            **kwargs
        )

        # 记录移交开始事件
        await self.record_event(
            create_trace_event(
                event_type=EventType.HANDOFF_START,
                node_id=from_agent_id,
                content={
                    "handoff_id": handoff_id,
                    "to_agent_role": to_agent_role
                },
                handoff_vector=handoff
            )
        )

        # 更新源节点的移交记录
        from_node = self.task_trace.get_node(from_agent_id)
        if from_node:
            from_node.handoffs.append(handoff)

        return handoff_id

    async def record_reflection(
        self,
        node_id: str,
        trigger_reason: str,
        reflection_content: str,
        suggested_improvements: List[str],
        confidence_score: float,
        **kwargs
    ) -> str:
        """记录反思过程"""
        reflection_id = str(uuid.uuid4())

        reflection = ReflectionTrace(
            reflection_id=reflection_id,
            timestamp=datetime.utcnow(),
            trigger_reason=trigger_reason,
            reflection_content=reflection_content,
            suggested_improvements=suggested_improvements,
            confidence_score=confidence_score,
            **kwargs
        )

        await self.record_event(
            create_trace_event(
                event_type=EventType.REFLECTION_COMPLETE,
                node_id=node_id,
                content={
                    "reflection_id": reflection_id,
                    "trigger_reason": trigger_reason
                },
                reflection_trace=reflection
            )
        )

        return reflection_id

    async def record_benchmark_context(
        self,
        node_id: str,
        benchmark_name: str,
        available_commands: Optional[List[str]] = None,
        observation: Optional[str] = None,
        background: Optional[str] = None,
        **kwargs
    ) -> None:
        """记录 Benchmark 上下文"""
        benchmark_context = BenchmarkContext(
            benchmark_name=benchmark_name,
            available_commands=available_commands,
            observation=observation,
            background=background,
            **kwargs
        )

        # 更新节点的 benchmark 上下文
        node = self.task_trace.get_node(node_id)
        if node:
            node.benchmark_context = benchmark_context

    async def record_dynamic_memory(
        self,
        node_id: str,
        short_term: List[str],
        long_term: List[Dict[str, Any]],
        working: Dict[str, Any],
        **kwargs
    ) -> None:
        """记录动态记忆快照"""
        memory = DynamicMemory(
            snapshot_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            short_term_memory=short_term,
            long_term_memory=long_term,
            working_memory=working,
            **kwargs
        )

        # 更新节点的动态记忆
        node = self.task_trace.get_node(node_id)
        if node:
            node.dynamic_memory = memory

    # ===== Query Methods =====

    def get_node(self, node_id: str) -> Optional[AgentNodeState]:
        """获取节点"""
        return self.task_trace.get_node(node_id)

    def get_events_for_node(self, node_id: str) -> List[TraceEvent]:
        """获取节点的所有事件"""
        return self.task_trace.get_events_for_node(node_id)

    def get_execution_tree(self) -> Dict[str, Any]:
        """获取执行树（用于前端可视化）"""
        return self.task_trace.get_execution_tree()

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "trace_id": self.task_trace.trace_id,
            "task_name": self.task_trace.task_name,
            "duration_ms": self.task_trace.duration_ms,
            "total_nodes": self.task_trace.total_nodes,
            "total_events": self.task_trace.total_events,
            "total_llm_calls": self.task_trace.total_llm_calls,
            "total_tool_calls": self.task_trace.total_tool_calls,
            "total_tokens_used": self.task_trace.total_tokens_used,
            "total_cost_usd": self.task_trace.total_cost_usd,
            "success": self.task_trace.success
        }

    # ===== Save & Export =====

    async def save(self) -> None:
        """保存追踪数据"""
        if not self.output_dir:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 保存完整的 JSON
        json_path = self.output_dir / f"trace_{self.task_trace.trace_id}.json"
        self.task_trace.save_to_file(str(json_path))

        # 保存执行树（用于前端）
        tree_path = self.output_dir / f"trace_{self.task_trace.trace_id}_tree.json"
        with open(tree_path, 'w', encoding='utf-8') as f:
            json.dump(self.get_execution_tree(), f, indent=2, ensure_ascii=False)

        # 保存统计摘要
        stats_path = self.output_dir / f"trace_{self.task_trace.trace_id}_stats.json"
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.get_statistics(), f, indent=2, ensure_ascii=False)

    async def finalize(self, success: bool = True, final_result: Optional[Dict[str, Any]] = None) -> None:
        """完成追踪"""
        self.task_trace.success = success
        self.task_trace.final_result = final_result
        self.task_trace.finalize()
        await self.save()

    # ===== Context Manager =====

    @asynccontextmanager
    async def trace_node(
        self,
        node_type: NodeType,
        role: str,
        system_prompt: str,
        user_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        parent_id: Optional[str] = None
    ):
        """上下文管理器：自动追踪节点的创建和完成"""
        node_id = await self.create_node(
            node_type=node_type,
            role=role,
            system_prompt=system_prompt,
            user_messages=user_messages,
            tools=tools,
            parent_id=parent_id
        )

        await self.start_node(node_id)

        try:
            yield node_id
            await self.complete_node(node_id, success=True)
        except Exception as e:
            await self.complete_node(node_id, success=False)
            # 更新节点的错误信息
            node = self.get_node(node_id)
            if node:
                node.error_message = str(e)
            raise


# ===== Global Tracing Instance =====

_global_tracing_manager: Optional[TracingManager] = None


def get_global_tracing() -> Optional[TracingManager]:
    """获取全局追踪管理器"""
    return _global_tracing_manager


def set_global_tracing(manager: TracingManager) -> None:
    """设置全局追踪管理器"""
    global _global_tracing_manager
    _global_tracing_manager = manager


def clear_global_tracing() -> None:
    """清除全局追踪管理器"""
    global _global_tracing_manager
    _global_tracing_manager = None
