"""
Agent Execution Tracing Schema

全链路追踪协议数据结构，用于捕获 Agent 系统的完整执行过程。
支持前端的"去黑箱化"可视化展示。

Design Principles:
1. 树形结构：保留 Agent 调用的层次关系
2. 时间序列：按时间顺序记录所有事件
3. 关联性：通过 ID 关联父子关系和相关事件
4. 扩展性：支持自定义字段和元数据
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
from enum import Enum
import json
import uuid


# ===== Enums =====

class NodeType(str, Enum):
    """Agent 节点类型"""
    ROOT = "root"                # 根 Agent
    MANAGER = "manager"          # 管理/协调 Agent
    WORKER = "worker"            # 工作执行 Agent
    HUMAN = "human"              # 人类用户
    REFLECTION = "reflection"    # 反思 Agent
    TOOL_EXECUTOR = "tool_executor"  # 工具执行 Agent


class NodeStatus(str, Enum):
    """Agent 节点状态"""
    IDLE = "idle"                # 空闲
    THINKING = "thinking"        # 思考中（LLM 调用）
    RUNNING = "running"          # 执行中
    WAITING = "waiting"          # 等待子 Agent
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 失败
    INTERRUPTED = "interrupted"  # 被中断


class EventType(str, Enum):
    """事件类型"""
    # Agent 生命周期事件
    NODE_CREATED = "node_created"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_INTERRUPTED = "node_interrupted"

    # LLM 调用事件
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_COMPLETE = "llm_call_complete"
    LLM_CALL_ERROR = "llm_call_error"

    # 工具调用事件
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    TOOL_CALL_ERROR = "tool_call_error"

    # 消息传递事件
    MESSAGE_SEND = "message_send"
    MESSAGE_RECEIVE = "message_receive"

    # Handoff 事件
    HANDOFF_START = "handoff_start"
    HANDOFF_COMPLETE = "handoff_complete"

    # 缓存事件
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"

    # 反思事件
    REFLECTION_START = "reflection_start"
    REFLECTION_COMPLETE = "reflection_complete"

    # 心跳事件
    HEARTBEAT = "heartbeat"


class CacheStatus(str, Enum):
    """缓存状态"""
    HIT = "hit"                  # 完全命中
    PARTIAL = "partial"          # 部分命中
    MISS = "miss"                # 未命中
    DISABLED = "disabled"        # 未启用缓存


# ===== Core Data Structures =====

@dataclass
class PromptCachingInfo:
    """
    提示词缓存信息

    捕获 LLM 调用的缓存命中状态，用于成本和效率分析。
    """
    status: CacheStatus
    cache_hit_position: Optional[int] = None  # 命中缓存的起始位置（token 索引）
    cache_hit_tokens: int = 0                 # 命中缓存的 token 数量
    total_tokens: int = 0                     # 总 token 数量
    cache_key: Optional[str] = None           # 缓存键（用于调试）
    cache_hit_percentage: float = 0.0         # 缓存命中率百分比

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "cache_hit_position": self.cache_hit_position,
            "cache_hit_tokens": self.cache_hit_tokens,
            "total_tokens": self.total_tokens,
            "cache_key": self.cache_key,
            "cache_hit_percentage": self.cache_hit_percentage
        }


@dataclass
class ToolCallRecord:
    """
    工具调用记录

    记录 Agent 发起的具体 Tool 调用及其参数和结果。
    """
    call_id: str
    tool_name: str                              # 工具名称（如 "send", "create", "code_gen"）
    arguments: Dict[str, Any]                   # 调用参数
    start_time: datetime
    end_time: Optional[datetime] = None
    status: Literal["pending", "success", "error"] = "pending"
    result: Optional[Dict[str, Any]] = None     # 调用结果
    error_message: Optional[str] = None         # 错误信息
    execution_time_ms: float = 0.0              # 执行耗时（毫秒）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "result": self.result,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata
        }


@dataclass
class HandoffVector:
    """
    移交向量

    记录任务被移交给哪个子 Agent，以及移交的上下文。
    """
    handoff_id: str
    from_agent_id: str                           # 来源 Agent ID
    to_agent_id: str                             # 目标 Agent ID
    to_agent_role: str                           # 目标 Agent 角色
    timestamp: datetime
    message_content: str                         # 移交消息内容
    context_transferred: List[str] = field(default_factory=list)  # 传递的上下文项
    response_required: bool = True               # 是否需要响应返回

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "from_agent_id": self.from_agent_id,
            "to_agent_id": self.to_agent_id,
            "to_agent_role": self.to_agent_role,
            "timestamp": self.timestamp.isoformat(),
            "message_content": self.message_content,
            "context_transferred": self.context_transferred,
            "response_required": self.response_required
        }


@dataclass
class LLMApiCallTrace:
    """
    LLM API 调用追踪

    完整记录 LLM API 的思考过程。
    """
    call_id: str
    timestamp: datetime
    model: str                                   # 模型名称（如 "gpt-4", "claude-3-opus"）
    messages: List[Dict[str, Any]]              # 完整的消息数组
    tools: Optional[List[Dict[str, Any]]] = None  # 可用的工具定义
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    # 思考过程
    thinking_time_ms: float = 0.0               # 思考耗时
    reasoning_steps: List[str] = field(default_factory=list)  # 推理步骤（如果模型提供）

    # API 响应
    response_content: str = ""                  # 响应内容
    tool_calls: Optional[List[Dict[str, Any]]] = None  # 工具调用
    finish_reason: Optional[str] = None         # 完成原因

    # Token 使用
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # 缓存信息
    cache_info: Optional[PromptCachingInfo] = None

    # 性能指标
    latency_ms: float = 0.0                     # API 延迟
    ttft_ms: Optional[float] = None             # Time to First Token

    # 错误信息
    error: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "messages": self.messages,
            "tools": self.tools,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "thinking_time_ms": self.thinking_time_ms,
            "reasoning_steps": self.reasoning_steps,
            "response_content": self.response_content,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cache_info": self.cache_info.to_dict() if self.cache_info else None,
            "latency_ms": self.latency_ms,
            "ttft_ms": self.ttft_ms,
            "error": self.error,
            "retry_count": self.retry_count
        }


@dataclass
class BenchmarkContext:
    """
    Benchmark 上下文信息

    捕获 Benchmark 环境的观察和可用命令。
    """
    benchmark_name: str                         # Benchmark 名称（如 "alfworld", "webshop"）
    task_type: Optional[str] = None             # 任务类型

    # ALFWorld 特定字段
    available_commands: Optional[List[str]] = None  # 可用命令列表
    observation: Optional[str] = None           # 当前观察
    background: Optional[str] = None            # 任务背景

    # WebShop 特定字段
    search_results: Optional[List[Dict]] = None
    product_info: Optional[Dict] = None

    # 通用字段
    step_number: int = 0                        # 当前步数
    max_steps: int = 100                        # 最大步数
    reward: float = 0.0                         # 当前奖励
    done: bool = False                          # 是否完成
    won: bool = False                           # 是否获胜

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "task_type": self.task_type,
            "available_commands": self.available_commands,
            "observation": self.observation,
            "background": self.background,
            "search_results": self.search_results,
            "product_info": self.product_info,
            "step_number": self.step_number,
            "max_steps": self.max_steps,
            "reward": self.reward,
            "done": self.done,
            "won": self.won,
            "metadata": self.metadata
        }


@dataclass
class ReflectionTrace:
    """
    反思追踪

    记录 Reflection Agent 的反思过程和结果。
    """
    reflection_id: str
    timestamp: datetime
    trigger_reason: str                         # 触发反思的原因

    # 反思的输入
    original_action: Optional[str] = None       # 原始动作
    action_result: Optional[Dict[str, Any]] = None  # 动作结果
    agent_state: Optional[Dict[str, Any]] = None  # Agent 当时的状态

    # 反思过程
    reflection_prompt: str = ""                 # 反思提示词
    thinking_process: List[str] = field(default_factory=list)  # 思考过程

    # 反思结果
    reflection_content: str = ""                # 反思内容
    suggested_improvements: List[str] = field(default_factory=list)  # 改进建议
    confidence_score: float = 0.0               # 置信度分数
    should_retry: bool = False                  # 是否建议重试

    # 性能指标
    reflection_time_ms: float = 0.0
    llm_calls: int = 0
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "timestamp": self.timestamp.isoformat(),
            "trigger_reason": self.trigger_reason,
            "original_action": self.original_action,
            "action_result": self.action_result,
            "agent_state": self.agent_state,
            "reflection_prompt": self.reflection_prompt,
            "thinking_process": self.thinking_process,
            "reflection_content": self.reflection_content,
            "suggested_improvements": self.suggested_improvements,
            "confidence_score": self.confidence_score,
            "should_retry": self.should_retry,
            "reflection_time_ms": self.reflection_time_ms,
            "llm_calls": self.llm_calls,
            "tokens_used": self.tokens_used
        }


@dataclass
class DynamicMemory:
    """
    动态记忆快照

    捕获 Agent 在当前时钟周期内的局部记忆状态。
    """
    snapshot_id: str
    timestamp: datetime

    # 记忆内容
    short_term_memory: List[str] = field(default_factory=list)  # 短期记忆（最近的思考）
    long_term_memory: List[Dict[str, Any]] = field(default_factory=list)  # 长期记忆（持久化知识）
    working_memory: Dict[str, Any] = field(default_factory=dict)  # 工作记忆（当前任务上下文）

    # 记忆统计
    total_memories: int = 0
    memory_size_bytes: int = 0                 # 估算的内存大小

    # 重要度评分
    importance_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "short_term_memory": self.short_term_memory,
            "long_term_memory": self.long_term_memory,
            "working_memory": self.working_memory,
            "total_memories": self.total_memories,
            "memory_size_bytes": self.memory_size_bytes,
            "importance_scores": self.importance_scores
        }


@dataclass
class TraceEvent:
    """
    追踪事件

    记录系统中发生的所有事件。
    """
    event_id: str
    event_type: EventType
    timestamp: datetime
    node_id: str                                # 关联的 Agent 节点 ID

    # 事件内容
    content: Dict[str, Any] = field(default_factory=dict)

    # 关联信息
    related_event_ids: List[str] = field(default_factory=list)  # 相关的事件 ID
    parent_event_id: Optional[str] = None       # 父事件 ID（用于因果链）

    # 数据负载（根据事件类型不同，负载不同）
    llm_call_trace: Optional[LLMApiCallTrace] = None
    tool_call_record: Optional[ToolCallRecord] = None
    handoff_vector: Optional[HandoffVector] = None
    reflection_trace: Optional[ReflectionTrace] = None
    benchmark_context: Optional[BenchmarkContext] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "node_id": self.node_id,
            "content": self.content,
            "related_event_ids": self.related_event_ids,
            "parent_event_id": self.parent_event_id,
            "llm_call_trace": self.llm_call_trace.to_dict() if self.llm_call_trace else None,
            "tool_call_record": self.tool_call_record.to_dict() if self.tool_call_record else None,
            "handoff_vector": self.handoff_vector.to_dict() if self.handoff_vector else None,
            "reflection_trace": self.reflection_trace.to_dict() if self.reflection_trace else None,
            "benchmark_context": self.benchmark_context.to_dict() if self.benchmark_context else None,
            "metadata": self.metadata
        }


@dataclass
class AgentNodeState:
    """
    Agent 节点状态（核心数据结构）

    捕获每个 Agent 的完整状态信息。
    """
    # 基本信息
    node_id: str                                 # 唯一标识符
    node_type: NodeType                          # 节点类型
    role: str                                    # 具体角色（如 "navigation_worker", "task_coordinator"）

    # System Prompts 和 Messages
    system_prompt: str                           # 系统提示词
    user_messages: List[Dict[str, Any]]          # 用户消息数组（历史对话）
    tools: List[Dict[str, Any]]                  # 可用的工具定义

    # 状态信息
    status: NodeStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 层级关系
    parent_id: Optional[str] = None              # 父 Agent ID
    child_ids: List[str] = field(default_factory=list)  # 子 Agent ID 列表
    depth: int = 0                               # 嵌套深度

    # 执行上下文
    dynamic_memory: Optional[DynamicMemory] = None     # 动态记忆快照
    benchmark_context: Optional[BenchmarkContext] = None  # Benchmark 上下文

    # 性能指标
    total_execution_time_ms: float = 0.0         # 总执行时间
    llm_call_count: int = 0                      # LLM 调用次数
    tool_call_count: int = 0                     # 工具调用次数
    total_tokens_used: int = 0                   # 总 token 消耗
    total_cost_usd: float = 0.0                  # 总成本（美元）

    # 子 Agent 和移交
    handoffs: List[HandoffVector] = field(default_factory=list)  # 移交记录

    # 错误信息
    error_message: Optional[str] = None
    error_stack: Optional[str] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "role": self.role,
            "system_prompt": self.system_prompt,
            "user_messages": self.user_messages,
            "tools": self.tools,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "depth": self.depth,
            "dynamic_memory": self.dynamic_memory.to_dict() if self.dynamic_memory else None,
            "benchmark_context": self.benchmark_context.to_dict() if self.benchmark_context else None,
            "total_execution_time_ms": self.total_execution_time_ms,
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "handoffs": [h.to_dict() for h in self.handoffs],
            "error_message": self.error_message,
            "error_stack": self.error_stack,
            "metadata": self.metadata
        }


@dataclass
class TaskTrace:
    """
    任务执行追踪（根对象）

    完整记录整个任务执行的过程，包括所有 Agent 的协作。
    """
    # 基本信息
    trace_id: str                                # 唯一追踪 ID
    task_name: str                               # 任务名称
    task_description: str                        # 任务描述

    # 时间信息
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # 根节点
    root_node: Optional[AgentNodeState] = None

    # 所有节点（扁平化存储，便于查询）
    all_nodes: Dict[str, AgentNodeState] = field(default_factory=dict)

    # 所有事件（按时间顺序）
    events: List[TraceEvent] = field(default_factory=list)

    # 统计信息
    total_nodes: int = 0                         # 总节点数
    total_events: int = 0                        # 总事件数
    total_llm_calls: int = 0                     # 总 LLM 调用数
    total_tool_calls: int = 0                    # 总工具调用数
    total_tokens_used: int = 0                   # 总 token 消耗
    total_cost_usd: float = 0.0                  # 总成本

    # 最终结果
    success: bool = False
    final_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: AgentNodeState) -> None:
        """添加节点"""
        self.all_nodes[node.node_id] = node
        self.total_nodes = len(self.all_nodes)
        if node.depth == 0 and not self.root_node:
            self.root_node = node

    def add_event(self, event: TraceEvent) -> None:
        """添加事件"""
        self.events.append(event)
        self.total_events = len(self.events)

        # 更新统计
        if event.event_type == EventType.LLM_CALL_COMPLETE:
            self.total_llm_calls += 1
            if event.llm_call_trace:
                self.total_tokens_used += event.llm_call_trace.total_tokens

        elif event.event_type == EventType.TOOL_CALL_COMPLETE:
            self.total_tool_calls += 1

    def get_node(self, node_id: str) -> Optional[AgentNodeState]:
        """获取节点"""
        return self.all_nodes.get(node_id)

    def get_events_for_node(self, node_id: str) -> List[TraceEvent]:
        """获取特定节点的所有事件"""
        return [e for e in self.events if e.node_id == node_id]

    def get_execution_tree(self) -> Dict[str, Any]:
        """获取执行树（用于前端可视化）"""
        if not self.root_node:
            return {}

        def build_tree(node: AgentNodeState) -> Dict[str, Any]:
            children = []
            for child_id in node.child_ids:
                child = self.all_nodes.get(child_id)
                if child:
                    children.append(build_tree(child))

            # 获取事件并转换为字典
            events = self.get_events_for_node(node.node_id)

            return {
                "node": node.to_dict(),
                "children": children,
                "events": [event.to_dict() for event in events]
            }

        return build_tree(self.root_node)

    def finalize(self) -> None:
        """完成追踪，计算最终统计"""
        self.completed_at = datetime.utcnow()
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

        # 累加所有节点的统计
        for node in self.all_nodes.values():
            self.total_tokens_used += node.total_tokens_used
            self.total_cost_usd += node.total_cost_usd

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "trace_id": self.trace_id,
            "task_name": self.task_name,
            "task_description": self.task_description,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "root_node": self.root_node.to_dict() if self.root_node else None,
            "all_nodes": {nid: n.to_dict() for nid, n in self.all_nodes.items()},
            "events": [e.to_dict() for e in self.events],
            "total_nodes": self.total_nodes,
            "total_events": self.total_events,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens_used": self.total_tokens_used,
            "total_cost_usd": self.total_cost_usd,
            "success": self.success,
            "final_result": self.final_result,
            "error_message": self.error_message,
            "metadata": self.metadata
        }

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save_to_file(self, filepath: str) -> None:
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


# ===== Factory Functions =====

def create_trace_event(
    event_type: EventType,
    node_id: str,
    content: Optional[Dict[str, Any]] = None,
    **kwargs
) -> TraceEvent:
    """创建追踪事件的工厂函数"""
    return TraceEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=datetime.utcnow(),
        node_id=node_id,
        content=content or {},
        **kwargs
    )


def create_agent_node(
    node_type: NodeType,
    role: str,
    system_prompt: str,
    user_messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    parent_id: Optional[str] = None,
    depth: int = 0,
    **kwargs
) -> AgentNodeState:
    """创建 Agent 节点的工厂函数"""
    return AgentNodeState(
        node_id=str(uuid.uuid4()),
        node_type=node_type,
        role=role,
        system_prompt=system_prompt,
        user_messages=user_messages,
        tools=tools,
        status=NodeStatus.IDLE,
        created_at=datetime.utcnow(),
        parent_id=parent_id,
        depth=depth,
        **kwargs
    )


def create_task_trace(
    task_name: str,
    task_description: str,
    **kwargs
) -> TaskTrace:
    """创建任务追踪的工厂函数"""
    return TaskTrace(
        trace_id=str(uuid.uuid4()),
        task_name=task_name,
        task_description=task_description,
        started_at=datetime.utcnow(),
        **kwargs
    )
