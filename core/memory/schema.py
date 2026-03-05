"""
Memory Entry Schemas for Auto-Expansion Agent Cluster.

Structured memory entries with cache-friendly storage layout.
Header fields (entry_id, memory_type, domain, task_type, agent_name, created_at)
form a stable prefix; content and metadata are the dynamic body.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class MemoryType(Enum):
    """Memory tier classification."""

    SHORT_TERM = "short_term"  # Recent observations/actions (rolling window)
    LONG_TERM = "long_term"  # Persistent knowledge/lessons learned
    WORKING = "working"  # Current task context
    REFLECTION = "reflection"  # Structured reflection outputs


@dataclass
class MemoryEntry:
    """
    A single memory entry with structured fields for routing and cache hits.

    The 'header' fields (entry_id, memory_type, domain, task_type, agent_name,
    created_at) form a STABLE PREFIX for cache-friendly storage.
    The 'content' and 'metadata' are the DYNAMIC BODY.
    """

    # Header (stable prefix)
    entry_id: str
    memory_type: MemoryType
    domain: str  # e.g., "manipulation", "navigation"
    task_type: str  # e.g., "pick_and_place", "clean"
    agent_name: str  # Which agent created this
    created_at: str  # ISO format timestamp

    # Content (dynamic body)
    content: str  # Main content
    tags: List[str] = field(default_factory=list)  # Routing tags
    importance: float = 0.5  # 0.0-1.0, used for pruning

    # Metadata
    source_task_id: Optional[str] = None
    source_episode_id: Optional[str] = None
    ttl_hours: Optional[float] = None  # Time-to-live for auto-expiry
    access_count: int = 0
    last_accessed: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict with enum conversion."""
        d = asdict(self)
        d["memory_type"] = self.memory_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize from dict with enum conversion."""
        data = data.copy()
        data["memory_type"] = MemoryType(data["memory_type"])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl_hours is None:
            return False
        created = datetime.fromisoformat(self.created_at)
        elapsed = (datetime.utcnow() - created).total_seconds() / 3600
        return elapsed > self.ttl_hours


@dataclass
class ReflectionMemoryEntry(MemoryEntry):
    """
    Structured reflection entry — extends MemoryEntry with fixed analysis fields.

    These fixed fields enable efficient routing without parsing free-text.
    """

    failure_type: str = ""  # e.g., "wrong_object", "missing_step", "tool_error"
    root_cause: str = ""  # Brief root cause
    tools_involved: List[str] = field(default_factory=list)
    prompt_section_to_update: str = (
        ""  # e.g., "error_prevention", "tool_specifications"
    )
    retry_recommendation: bool = False
    confidence: float = 0.0  # 0.0-1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict, including reflection-specific fields."""
        d = super().to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionMemoryEntry":
        """Deserialize from dict with enum conversion."""
        data = data.copy()
        data["memory_type"] = MemoryType(data["memory_type"])
        return cls(**data)


@dataclass
class MemoryQuery:
    """
    Query for retrieving memories. Fields act as filters.

    None fields are ignored (match all).
    """

    domain: Optional[str] = None
    task_type: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    agent_name: Optional[str] = None
    tags: Optional[List[str]] = None  # Match any of these tags
    min_importance: float = 0.0
    limit: int = 10
    include_expired: bool = False
