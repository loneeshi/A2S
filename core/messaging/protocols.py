"""
Message protocol definitions for Agent communication.

Defines message types, tools, and data structures following swarm-ide patterns.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class MessageType(str, Enum):
    """Message content types."""
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"


class ToolCall(BaseModel):
    """Represents a tool call from an agent."""
    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI tool call format."""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments)
            }
        }


class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_call_id: str
    ok: bool
    result: Any
    error: Optional[str] = None


class AgentMessage(BaseModel):
    """Message between agents."""
    id: str
    workspace_id: str
    group_id: str
    sender_id: str
    content_type: MessageType
    content: str
    send_time: datetime = datetime.utcnow()
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None

    def to_history_format(self) -> Dict[str, Any]:
        """
        Convert to LLM history format.

        Returns:
            Dictionary in OpenAI chat completion format
        """
        if self.content_type == MessageType.TOOL_RESULT:
            return {
                "role": "tool",
                "content": self.content,
                "tool_call_id": self.tool_call_id,
                "name": self.tool_name
            }
        elif self.content_type == MessageType.TOOL_CALL:
            # Parse tool call from content
            try:
                data = json.loads(self.content)
                return {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": self.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": self.tool_name,
                                "arguments": json.dumps(data.get("arguments", {}))
                            }
                        }
                    ]
                }
            except json.JSONDecodeError:
                return {
                    "role": "assistant",
                    "content": self.content
                }
        else:
            # TEXT or SYSTEM
            # Use "user" role for human messages, "assistant" for agent messages
            role = "user" if self.sender_id == "human" else "assistant"
            return {
                "role": role,
                "content": self.content
            }

    @classmethod
    def from_user_input(
        cls,
        content: str,
        workspace_id: str,
        group_id: str,
        sender_id: str = "human"
    ) -> "AgentMessage":
        """Create a message from user input."""
        import uuid
        return cls(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            group_id=group_id,
            sender_id=sender_id,
            content_type=MessageType.TEXT,
            content=content
        )


class HistoryMessage(BaseModel):
    """
    Message in Agent's LLM history.

    Compatible with OpenAI chat completion format.
    """
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "role": self.role,
            "content": self.content
        }

        if self.tool_calls:
            result["tool_calls"] = self.tool_calls

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        if self.name:
            result["name"] = self.name

        return result

    @classmethod
    def system(cls, content: str) -> "HistoryMessage":
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "HistoryMessage":
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: Optional[List[Dict]] = None) -> "HistoryMessage":
        """Create an assistant message."""
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, name: str) -> "HistoryMessage":
        """Create a tool result message."""
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name
        )
