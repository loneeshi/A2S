"""
Cache-Optimized Prompt Builder for Auto-Expansion Agent Cluster

Following vLLM semantic-router best practices:
- Static content (system prompt) comes FIRST
- Dynamic content (examples) comes LAST
- XML tags for clear section marking

Target cache hit rate: 70-80%
"""

from typing import Dict, List, Any, Optional


def _try_get_cache_manager():
    """Lazy import to avoid circular dependency."""
    try:
        from .cache_manager import get_prompt_cache_manager

        return get_prompt_cache_manager()
    except Exception:
        return None


class CacheOptimizedPromptBuilder:
    """
    Build prompts with static/dynamic separation for cache hits

    Key Principle:
    - First 1024 tokens must be identical for cache hits
    - Static prefix: Shared across all agents in a domain
    - Role structure: Shared by agents with same role
    - Dynamic examples: Task-specific (breaks cache but necessary)

    Assembly Order:
    1. STATIC_PREFIX (always first, high cache hit)
    2. ROLE_STRUCTURE (middle, medium cache hit)
    3. DYNAMIC_EXAMPLES (last, no cache, but necessary)
    """

    def __init__(self, domain: str):
        """
        Initialize prompt builder for a specific domain.

        Args:
            domain: Domain name (e.g., "navigation", "email", "course")
        """
        self.domain = domain
        self.static_prefix = ""
        self.role_structures: Dict[str, str] = {}
        self.dynamic_examples: Dict[str, str] = {}
        self._load_static_prefix(domain)

    def _load_static_prefix(self, domain: str) -> None:
        """Load static prefix for domain"""
        # Import from static_prefixes module
        try:
            from core.prompts.static_prefixes import get_static_prefix

            self.static_prefix = get_static_prefix(domain)
        except (ImportError, ValueError):
            # Fallback: create minimal static prefix
            self.static_prefix = self._create_default_static_prefix(domain)

    def _create_default_static_prefix(self, domain: str) -> str:
        """Create default static prefix for domain"""
        return f"""
<role_definition>
You are a {domain} specialist in the agent cluster.
You work within the {domain} domain to accomplish specific tasks efficiently.
</role_definition>

<core_protocol>
## {domain.capitalize()} Protocol (v1.0)

### Core Rules
1. Follow instructions precisely
2. Use tools correctly with proper parameters
3. Verify results before proceeding
4. Report failures clearly
</core_protocol>

<workflow_structure>
## Standard {domain.capitalize()} Workflow

### Phase 1: Understand Task
- Read task description carefully
- Extract requirements and constraints
- Identify required tools

### Phase 2: Execute
- Use appropriate tools
- Follow proper sequence
- Verify each step

### Phase 3: Complete
- Confirm task completion
- Report results
</workflow_structure>
"""

    def add_role_structure(self, role: str, structure: str) -> None:
        """Add role-specific structure"""
        self.role_structures[role] = structure

    def add_dynamic_examples(self, role: str, examples: str) -> None:
        """Add dynamic examples for a role"""
        self.dynamic_examples[role] = examples

    def build_prompt(
        self,
        role: str,
        task_context: Optional[Dict[str, Any]] = None,
        include_examples: bool = True,
        working_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build cache-optimized prompt

        Args:
            role: Agent role ("manager" | "worker")
            task_context: Task-specific context
            include_examples: Whether to include dynamic examples
            working_context: Optional working memory (lessons, errors, recent actions)

        Returns:
            Assembled prompt with cache-optimized structure
        """
        parts = [self.static_prefix]

        # Try loading cached static prefix from PromptCacheManager
        cache_mgr = _try_get_cache_manager()
        if cache_mgr:
            from .cache_manager import CacheTier

            cached = cache_mgr.get_cached_prompt(
                self.domain, role, CacheTier.STATIC_PREFIX
            )
            if cached:
                parts = [cached.content]

        # Add role-specific structure
        if role in self.role_structures:
            parts.append(self.role_structures[role])

        # Add working context (lessons learned, known errors)
        if working_context:
            parts.append(self._format_working_context(working_context))

        # Add dynamic examples last (breaks cache but necessary)
        if include_examples and task_context and role in self.dynamic_examples:
            examples = self._select_relevant_examples(
                self.dynamic_examples[role], task_context
            )
            if examples:
                parts.append(examples)

        return "\n\n" + "\n\n".join(parts)

    def _select_relevant_examples(
        self, all_examples: str, task_context: Dict[str, Any]
    ) -> str:
        """Select examples relevant to current task context"""
        # For now, return all examples
        # TODO: Implement smart example selection based on task_context
        return all_examples

    def _format_working_context(self, context: Dict[str, Any]) -> str:
        """Format working context for prompt injection."""
        sections = ["<working_memory>"]

        lessons = context.get("lessons_learned", [])
        if lessons:
            sections.append("## Lessons Learned")
            for lesson in lessons:
                sections.append(f"- {lesson}")

        errors = context.get("known_errors", [])
        if errors:
            sections.append("## Known Errors to Avoid")
            for err in errors:
                if isinstance(err, dict):
                    ft = err.get("failure_type", "")
                    rc = err.get("root_cause", "")
                    sections.append(f"- {ft}: {rc}")
                else:
                    sections.append(f"- {err}")

        recent = context.get("recent_actions", [])
        if recent:
            sections.append("## Recent Actions")
            for action in recent[-5:]:
                sections.append(f"- {action}")

        sections.append("</working_memory>")
        return "\n".join(sections)

    def estimate_cache_hit_potential(self, prompt: str) -> Dict[str, Any]:
        """
        Estimate cache hit potential of a prompt

        Returns:
            {
                "total_tokens": int,
                "static_tokens": int,
                "static_ratio": float,
                "cache_hit_potential": str  # "high" | "medium" | "low"
            }
        """
        # Simple heuristic: count lines in each section
        lines = prompt.split("\n")

        static_markers = [
            "<role_definition>",
            "<core_protocol>",
            "<workflow_structure>",
            "<tool_specifications>",
        ]

        dynamic_markers = ["<dynamic_examples>", "<current_task>"]

        static_lines = 0
        dynamic_lines = 0

        for line in lines:
            line_stripped = line.strip()
            if any(marker in line for marker in static_markers):
                static_lines += 1
            elif any(marker in line for marker in dynamic_markers):
                dynamic_lines += 1

        total_lines = len(lines)

        if total_lines == 0:
            static_ratio = 0.0
        else:
            static_ratio = static_lines / total_lines

        if static_ratio > 0.7:
            potential = "high"
        elif static_ratio > 0.5:
            potential = "medium"
        else:
            potential = "low"

        return {
            "total_tokens": total_lines * 10,  # Approximate: 10 tokens per line
            "static_tokens": static_lines * 10,
            "static_ratio": static_ratio,
            "cache_hit_potential": potential,
        }


def create_prompt_builder(domain: str) -> CacheOptimizedPromptBuilder:
    """Factory function to create prompt builder for a domain"""
    return CacheOptimizedPromptBuilder(domain)


# Convenience function
def build_prompt(
    domain: str,
    role: str,
    task_context: Optional[Dict[str, Any]] = None,
    include_examples: bool = True,
) -> str:
    """
    Convenience function to build prompt

    Args:
        domain: Domain name
        role: Agent role
        task_context: Task-specific context
        include_examples: Include dynamic examples

    Returns:
        Assembled prompt string
    """
    builder = create_prompt_builder(domain)
    return builder.build_prompt(role, task_context, include_examples)
