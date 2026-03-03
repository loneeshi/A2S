"""
Built-in Agent tools for inter-agent communication.

These tools are automatically available to all agents and implement
the swarm-ide messaging protocol.
"""

from typing import List, Dict, Any, Optional

# OpenAI-style tool definitions for builtin agent tools
BUILTIN_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "self",
            "description": "返回当前 Agent 的身份信息（agent_id, workspace_id, role）。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_agents",
            "description": "列出当前工作空间中的所有 Agent（ID + 角色）。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create",
            "description": "创建子 Agent 用于任务委派。返回 {agentId}。",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "新 Agent 的角色名称，例如 coder/researcher/reviewer"
                    },
                    "guidance": {
                        "type": "string",
                        "description": "额外的系统指导，用于初始化新 Agent。"
                    }
                },
                "required": ["role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send",
            "description": "向另一个 agent_id 发送直接消息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "目标 Agent ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "消息内容"
                    }
                },
                "required": ["to", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_groups",
            "description": "列出当前 Agent 可见的群组。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_group",
            "description": "创建包含指定成员 ID 的群组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memberIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要包含在群组中的 Agent ID 列表"
                    },
                    "name": {
                        "type": "string",
                        "description": "可选的群组名称"
                    }
                },
                "required": ["memberIds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_group_message",
            "description": "向群组发送消息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "groupId": {
                        "type": "string",
                        "description": "目标群组 ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "消息内容"
                    }
                },
                "required": ["groupId", "content"]
            }
        }
    }
]


def get_builtin_tool_names() -> List[str]:
    """Get list of builtin tool names."""
    return [tool["function"]["name"] for tool in BUILTIN_TOOLS]


def is_builtin_tool(tool_name: str) -> bool:
    """Check if a tool is a builtin tool."""
    return tool_name in get_builtin_tool_names()


def get_tool_definition(tool_name: str) -> Optional[Dict[str, Any]]:
    """Get definition of a builtin tool by name."""
    for tool in BUILTIN_TOOLS:
        if tool["function"]["name"] == tool_name:
            return tool
    return None
