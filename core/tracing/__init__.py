"""
Agent Execution Tracing System

全链路追踪系统，用于捕获和展示 Agent 系统的完整执行过程。
"""

from .schema import (
    # Enums
    NodeType,
    NodeStatus,
    EventType,
    CacheStatus,

    # Core Data Structures
    PromptCachingInfo,
    ToolCallRecord,
    HandoffVector,
    LLMApiCallTrace,
    BenchmarkContext,
    ReflectionTrace,
    DynamicMemory,
    TraceEvent,
    AgentNodeState,
    TaskTrace,

    # Factory Functions
    create_trace_event,
    create_agent_node,
    create_task_trace,
)

from .manager import (
    TracingManager,
    get_global_tracing,
    set_global_tracing,
    clear_global_tracing,
)

__all__ = [
    # Enums
    "NodeType",
    "NodeStatus",
    "EventType",
    "CacheStatus",

    # Core Data Structures
    "PromptCachingInfo",
    "ToolCallRecord",
    "HandoffVector",
    "LLMApiCallTrace",
    "BenchmarkContext",
    "ReflectionTrace",
    "DynamicMemory",
    "TraceEvent",
    "AgentNodeState",
    "TaskTrace",

    # Factory Functions
    "create_trace_event",
    "create_agent_node",
    "create_task_trace",

    # Manager
    "TracingManager",
    "get_global_tracing",
    "set_global_tracing",
    "clear_global_tracing",
]
