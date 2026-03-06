"""
AgentSpec Markdown Loader

Reads AgentSpec markdown files from the agenttree/agents directory,
parses YAML frontmatter and markdown body, and returns structured data.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _parse_yaml_frontmatter(content: str) -> tuple[Optional[Dict[str, Any]], str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Full markdown content with potential frontmatter

    Returns:
        Tuple of (frontmatter_dict, body_content)
        If no frontmatter found, returns (None, original_content)
    """
    # Match YAML frontmatter pattern: --- at start, content, then ---
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.match(pattern, content, re.DOTALL)

    if not match:
        return None, content

    frontmatter_text = match.group(1)
    body = match.group(2).strip()

    # Parse YAML
    if HAS_YAML:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
            return frontmatter, body
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML frontmatter: {e}")
    else:
        # Minimal YAML parser for simple cases
        frontmatter = _minimal_yaml_parse(frontmatter_text)
        return frontmatter, body


def _minimal_yaml_parse(text: str) -> Dict[str, Any]:
    """
    Minimal YAML parser for simple key-value pairs and lists.
    Handles basic AgentSpec frontmatter structure without external dependencies.

    Limitations:
    - No support for complex nested structures beyond 2 levels
    - No support for multi-line strings (use PyYAML for those)
    - No support for anchors, aliases, or advanced YAML features
    """
    result: Dict[str, Any] = {}
    lines = text.split("\n")
    current_key: Optional[str] = None
    current_dict: Optional[Dict[str, Any]] = None
    current_list: Optional[List[Any]] = None
    indent_stack: List[tuple[int, str, Any]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # Handle list items
        if stripped.startswith("- "):
            value = stripped[2:].strip()

            if current_list is not None:
                current_list.append(value)
            elif current_key:
                # Start a new list
                current_list = [value]
                if current_dict is not None:
                    current_dict[current_key] = current_list
                else:
                    result[current_key] = current_list
            continue

        # Handle key-value pairs
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            # Determine nesting level
            if indent == 0:
                # Top level
                current_key = key
                current_dict = None
                current_list = None

                if value:
                    result[key] = _parse_value(value)
                else:
                    # Empty value - likely a nested structure
                    result[key] = {}
                    current_dict = result[key]

            elif indent > 0 and current_key:
                # Nested level
                if current_dict is not None:
                    current_list = None  # Reset list when entering new key
                    if value:
                        current_dict[key] = _parse_value(value)
                    else:
                        # Nested dict
                        current_dict[key] = {}
                        # For deeper nesting, would need more sophisticated handling

    return result


def _parse_value(value: str) -> Any:
    """Parse a YAML value string to appropriate Python type."""
    value = value.strip()

    # Boolean
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False

    # None/null
    if value.lower() in ("null", "none", "~", ""):
        return None

    # Number
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # String (remove quotes if present)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]

    return value


def _find_agent_spec_files(base_dir: str) -> List[Path]:
    """
    Find all .md files under agents/ directory.

    Args:
        base_dir: Base directory (typically agenttree/)

    Returns:
        List of Path objects for found markdown files
    """
    agents_dir = Path(base_dir) / "agents"

    if not agents_dir.exists():
        return []

    # Recursively find all .md files
    md_files = list(agents_dir.rglob("*.md"))
    return md_files


def _load_agent_spec_file(file_path: Path) -> Dict[str, Any]:
    """
    Load and parse a single AgentSpec markdown file.

    Args:
        file_path: Path to the markdown file

    Returns:
        Dict with agent specification data
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    frontmatter, body = _parse_yaml_frontmatter(content)

    if frontmatter is None:
        raise ValueError(f"No frontmatter found in {file_path}")

    # Build the agent spec dict with all required fields
    spec = {
        "id": frontmatter.get("id"),
        "name": frontmatter.get("name"),
        "role": frontmatter.get("role"),
        "mode": frontmatter.get("mode"),
        "description": frontmatter.get("description"),
        "tools": frontmatter.get("tools", {}),
        "memory": frontmatter.get("memory", {}),
        "skills": frontmatter.get("skills", []),
        "metadata": frontmatter.get("metadata", {}),
        "prompt": body,
    }

    return spec


def load_agent_specs(base_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load all AgentSpec markdown files from the agenttree directory.

    Args:
        base_dir: Base directory path (default: auto_expansion_agent/agenttree)

    Returns:
        List of dicts, each containing:
            - id: Agent identifier
            - name: Agent display name
            - role: Agent role (worker, coordinator, etc.)
            - mode: Execution mode (subagent, etc.)
            - description: Agent description
            - tools: Tool configuration dict
            - memory: Memory configuration dict
            - skills: List of skill identifiers
            - metadata: Additional metadata dict
            - prompt: Markdown body content (system prompt)

    Raises:
        ValueError: If files cannot be parsed
        FileNotFoundError: If base_dir doesn't exist
    """
    # Default base directory
    if base_dir is None:
        base_dir = "/Users/dp/Agent_research/design/auto_expansion_agent/agenttree"

    base_path = Path(base_dir)
    if not base_path.exists():
        raise FileNotFoundError(f"Base directory not found: {base_dir}")

    # Find all agent spec files
    spec_files = _find_agent_spec_files(base_dir)

    # Load and parse each file
    specs = []
    for file_path in spec_files:
        try:
            spec = _load_agent_spec_file(file_path)
            specs.append(spec)
        except Exception as e:
            # Include file path in error for debugging
            raise ValueError(f"Failed to load {file_path}: {e}") from e

    return specs
