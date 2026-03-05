"""
Reflection Module for Auto-Expansion Agent Cluster

Provides structured failure analysis and prompt-update recommendations.
"""

from .schema import (
    ReflectionTrigger,
    PromptUpdateAction,
    ReflectionOutput,
)

from .agent import (
    ReflectionAgent,
    get_reflection_agent,
)

__all__ = [
    "ReflectionTrigger",
    "PromptUpdateAction",
    "ReflectionOutput",
    "ReflectionAgent",
    "get_reflection_agent",
]
