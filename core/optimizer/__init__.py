"""
Optimizer Module for Auto-Expansion Agent Cluster

This module handles dynamic optimization of agent trees during testing,
including performance monitoring and automatic extension.
"""

from .performance_monitor import (
    PerformanceMonitor,
    TaskStatus,
    TaskResult,
    AgentMetrics,
)

from .extension_engine import (
    DynamicExtensionEngine,
    ExtensionType,
    ExtensionProposal,
)

from .extension_hooks import (
    ExtensionHook,
    ExtensionRegistry,
    get_extension_registry,
)

__all__ = [
    "PerformanceMonitor",
    "TaskStatus",
    "TaskResult",
    "AgentMetrics",
    "DynamicExtensionEngine",
    "ExtensionType",
    "ExtensionProposal",
    "ExtensionHook",
    "ExtensionRegistry",
    "get_extension_registry",
]
