"""
Memory subsystem for Auto-Expansion Agent Cluster.

Provides structured memory storage (short-term, long-term, reflection)
with metadata-based semantic routing for efficient retrieval.
"""

from .schema import MemoryEntry, ReflectionMemoryEntry, MemoryQuery, MemoryType
from .manager import MemoryManager, get_memory_manager
from .router import SemanticRouter
from .semantic_cache import SemanticCache, EmbeddingBackend

__all__ = [
    "MemoryEntry",
    "ReflectionMemoryEntry",
    "MemoryQuery",
    "MemoryType",
    "MemoryManager",
    "get_memory_manager",
    "SemanticRouter",
    "SemanticCache",
    "EmbeddingBackend",
]
