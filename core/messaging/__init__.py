"""
Messaging system for Agent communication.

Provides message protocols and tools for inter-agent communication.
"""

from .protocols import (
    MessageType,
    AgentMessage,
    ToolCall,
    ToolResult,
)
from .tools import BUILTIN_TOOLS

__all__ = [
    "MessageType",
    "AgentMessage",
    "ToolCall",
    "ToolResult",
    "BUILTIN_TOOLS",
]
