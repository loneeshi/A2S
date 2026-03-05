"""
Structured Reflection Output Schemas

Defines typed, cache-friendly data structures for reflection analysis.
All fields are fixed/typed -- no free-text reflection_content field.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from enum import Enum
from datetime import datetime


class ReflectionTrigger(Enum):
    """What triggered the reflection."""

    TASK_FAILURE = "task_failure"
    LOW_SUCCESS_RATE = "low_success_rate"
    REPEATED_ERROR = "repeated_error"
    EXTENSION_TRIGGERED = "extension_triggered"
    MANUAL = "manual"


class PromptUpdateAction(Enum):
    """Which prompt tier/section should be updated."""

    UPDATE_ERROR_PREVENTION = "update_error_prevention"
    UPDATE_TOOL_SPECIFICATIONS = "update_tool_specifications"
    UPDATE_CORE_PROTOCOL = "update_core_protocol"
    UPDATE_WORKFLOW_STRUCTURE = "update_workflow_structure"
    ADD_DYNAMIC_EXAMPLE = "add_dynamic_example"
    NO_UPDATE = "no_update"


@dataclass
class ReflectionOutput:
    """
    Structured reflection output -- ALL fields are fixed/typed for cache-friendly storage.
    NO free-text reflection_content field. Everything is structured.
    """

    reflection_id: str
    timestamp: str  # ISO format
    trigger: ReflectionTrigger

    # What happened
    domain: str  # e.g., "manipulation", "navigation"
    task_type: str  # e.g., "pick_and_place"
    agent_name: str
    episode_id: Optional[str] = None

    # Analysis (structured, not free-text)
    failure_type: str = ""  # e.g., "wrong_object", "missing_step", "tool_misuse"
    root_cause: str = ""  # 1-2 sentence root cause
    tools_involved: List[str] = field(default_factory=list)
    error_pattern: str = ""  # Pattern name for deduplication

    # Recommendations (structured)
    prompt_update_action: PromptUpdateAction = PromptUpdateAction.NO_UPDATE
    prompt_update_content: str = ""  # Specific text to add/modify in prompt
    memory_updates: List[Dict[str, str]] = field(default_factory=list)
    # Each: {"type": "lesson"|"error_pattern"|"tool_tip", "content": "...", "tags": "tag1,tag2"}
    retry_recommendation: bool = False
    confidence: float = 0.0  # 0.0-1.0

    # Performance context
    success_rate_before: float = 0.0
    total_failures_analyzed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["trigger"] = self.trigger.value
        d["prompt_update_action"] = self.prompt_update_action.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionOutput":
        data = data.copy()
        data["trigger"] = ReflectionTrigger(data["trigger"])
        data["prompt_update_action"] = PromptUpdateAction(data["prompt_update_action"])
        return cls(**data)
