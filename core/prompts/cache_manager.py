"""
Prompt Cache Manager for Auto-Expansion Agent Cluster

This module manages systematic updates to agent prompts with cache optimization.

Core Features:
1. Three-tier prompt structure (static/role/dynamic)
2. Automatic cache invalidation and updates
3. LLM-driven prompt optimization
4. Version tracking and rollback

Target cache hit rate: 70-80% (first 1024-2048 tokens)
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """Prompt caching tiers"""
    STATIC_PREFIX = "static_prefix"      # 1200 tokens, HIGH cache hit (70-80%)
    ROLE_SPECIFIC = "role_specific"      # 200-400 tokens, MED cache hit (40-60%)
    DYNAMIC = "dynamic"                  # 100-300 tokens, NO cache hit


@dataclass
class CachedPrompt:
    """A cached prompt with version tracking"""
    domain: str
    role: str
    tier: CacheTier
    content: str
    version: int
    hash: str
    created_at: str
    usage_count: int = 0
    last_used: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PromptUpdateResult:
    """Result of a prompt update operation"""
    success: bool
    domain: str
    role: str
    old_version: Optional[int]
    new_version: int
    cache_hit_before: Optional[float]
    cache_hit_after: Optional[float]
    tokens_saved: int
    update_reason: str
    changes_made: List[str]


class PromptCacheManager:
    """
    Manage prompt caching with systematic updates

    This manager:
    1. Stores cached prompts by tier (static/role/dynamic)
    2. Tracks cache hit rates and performance
    3. Triggers updates when performance degrades
    4. Uses LLM to optimize prompts
    5. Maintains version history for rollback
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize prompt cache manager

        Args:
            cache_dir: Directory to store cached prompts (default: core/prompts/cache/)
        """
        if cache_dir is None:
            current_file = Path(__file__)
            cache_dir = current_file.parent / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories for each tier
        for tier in CacheTier:
            (self.cache_dir / tier.value).mkdir(exist_ok=True)

        # In-memory cache
        self.prompts: Dict[Tuple[str, str, CacheTier], CachedPrompt] = {}

        # Version history
        self.history: List[PromptUpdateResult] = []

        logger.info(f"PromptCacheManager initialized with cache dir: {self.cache_dir}")

    def get_cached_prompt(
        self,
        domain: str,
        role: str,
        tier: CacheTier
    ) -> Optional[CachedPrompt]:
        """
        Get cached prompt for a domain/role/tier combination

        Args:
            domain: Agent domain (e.g., "navigation", "manipulation")
            role: Agent role ("worker" | "manager")
            tier: Cache tier (STATIC_PREFIX | ROLE_SPECIFIC | DYNAMIC)

        Returns:
            CachedPrompt if found, None otherwise
        """
        key = (domain, role, tier)

        # Check in-memory cache first
        if key in self.prompts:
            prompt = self.prompts[key]
            prompt.usage_count += 1
            prompt.last_used = datetime.now().isoformat()
            return prompt

        # Load from disk
        cache_file = self._get_cache_file(domain, role, tier)
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                # Convert tier string back to enum
                if isinstance(data.get('tier'), str):
                    data['tier'] = CacheTier(data['tier'])
                prompt = CachedPrompt(**data)
                self.prompts[key] = prompt
                logger.debug(f"Loaded cached prompt: {domain}/{role}/{tier.value}")
                return prompt
            except Exception as e:
                logger.error(f"Failed to load cache file {cache_file}: {e}")

        return None

    def update_cached_prompt(
        self,
        domain: str,
        role: str,
        tier: CacheTier,
        content: str,
        update_reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PromptUpdateResult:
        """
        Update a cached prompt with version tracking

        Args:
            domain: Agent domain
            role: Agent role
            tier: Cache tier
            content: New prompt content
            update_reason: Reason for the update
            metadata: Additional metadata

        Returns:
            PromptUpdateResult with update details
        """
        # Get old version
        old_prompt = self.get_cached_prompt(domain, role, tier)
        old_version = old_prompt.version if old_prompt else None

        # Calculate new version
        new_version = (old_version + 1) if old_version is not None else 1

        # Create new cached prompt
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        new_prompt = CachedPrompt(
            domain=domain,
            role=role,
            tier=tier,
            content=content,
            version=new_version,
            hash=content_hash,
            created_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        # Save to disk and memory
        self._save_cached_prompt(new_prompt)
        key = (domain, role, tier)
        self.prompts[key] = new_prompt

        # Calculate cache hit improvement
        cache_hit_before = self._estimate_cache_hit_rate(old_prompt) if old_prompt else None
        cache_hit_after = self._estimate_cache_hit_rate(new_prompt)
        tokens_saved = self._estimate_token_savings(old_prompt, new_prompt)

        # Record result
        result = PromptUpdateResult(
            success=True,
            domain=domain,
            role=role,
            old_version=old_version,
            new_version=new_version,
            cache_hit_before=cache_hit_before,
            cache_hit_after=cache_hit_after,
            tokens_saved=tokens_saved,
            update_reason=update_reason,
            changes_made=self._analyze_changes(old_prompt, new_prompt)
        )

        self.history.append(result)

        logger.info(
            f"Updated prompt: {domain}/{role}/{tier.value} "
            f"v{old_version}→v{new_version} "
            f"(cache hit: {cache_hit_before}→{cache_hit_after}, "
            f"saved: {tokens_saved} tokens)"
        )

        return result

    def batch_update_from_tree(
        self,
        agent_tree,
        update_reason: str = "agent_tree_expansion"
    ) -> List[PromptUpdateResult]:
        """
        Update all prompts from an agent tree

        This is called when agent tree is extended to update prompts
        for new agents and optimize existing ones.

        Args:
            agent_tree: Updated agent tree
            update_reason: Reason for batch update

        Returns:
            List of PromptUpdateResult for each updated prompt
        """
        results = []

        # Update worker prompts
        for worker in agent_tree.workers:
            domain = worker.metadata.get("prompt_builder_domain", worker.domain)
            role = "worker"

            # Update static prefix if needed
            static_prompt = self.get_cached_prompt(
                domain, role, CacheTier.STATIC_PREFIX
            )

            if not static_prompt or self._needs_optimization(static_prompt):
                # Generate new static prefix
                new_content = self._generate_static_prefix(worker)
                result = self.update_cached_prompt(
                    domain=domain,
                    role=role,
                    tier=CacheTier.STATIC_PREFIX,
                    content=new_content,
                    update_reason=f"{update_reason}:new_worker",
                    metadata={"worker_name": worker.name, "tools": worker.tools}
                )
                results.append(result)

        # Update manager prompts
        for manager in agent_tree.managers:
            domain = manager.domain
            role = "manager"

            # Update role-specific prompts
            role_prompt = self.get_cached_prompt(
                domain, role, CacheTier.ROLE_SPECIFIC
            )

            if not role_prompt or self._needs_optimization(role_prompt):
                new_content = self._generate_role_specific(manager)
                result = self.update_cached_prompt(
                    domain=domain,
                    role=role,
                    tier=CacheTier.ROLE_SPECIFIC,
                    content=new_content,
                    update_reason=f"{update_reason}:new_manager",
                    metadata={"manager_name": manager.name}
                )
                results.append(result)

        logger.info(f"Batch update completed: {len(results)} prompts updated")
        return results

    def build_prompt_for_agent(
        self,
        agent,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build complete prompt for an agent by combining tiers

        Args:
            agent: Agent definition
            task_context: Current task context for dynamic tier

        Returns:
            Tuple of (complete_prompt, cache_metadata)
        """
        domain = agent.metadata.get("prompt_builder_domain", agent.domain)
        role = agent.role

        # Get static prefix
        static_prompt = self.get_cached_prompt(domain, role, CacheTier.STATIC_PREFIX)
        if not static_prompt:
            # Generate default static prefix
            static_content = self._generate_default_static_prefix(domain)
            static_prompt = self.update_cached_prompt(
                domain, role, CacheTier.STATIC_PREFIX,
                static_content, "default_generation"
            )

        # Get role-specific
        role_prompt = self.get_cached_prompt(domain, role, CacheTier.ROLE_SPECIFIC)

        # Build dynamic content
        dynamic_content = self._build_dynamic_content(agent, task_context)

        # Combine tiers
        parts = [static_prompt.content]
        if role_prompt:
            parts.append(role_prompt.content)
        parts.append(dynamic_content)

        complete_prompt = "\n\n".join(parts)

        # Calculate cache metadata
        metadata = {
            "static_tokens": len(static_prompt.content) // 4,
            "role_tokens": len(role_prompt.content) // 4 if role_prompt else 0,
            "dynamic_tokens": len(dynamic_content) // 4,
            "total_tokens": len(complete_prompt) // 4,
            "cache_hit_potential": self._calculate_cache_hit_potential(
                len(static_prompt.content),
                len(role_prompt.content) if role_prompt else 0,
                len(dynamic_content)
            )
        }

        return complete_prompt, metadata

    def analyze_cache_performance(self) -> Dict[str, Any]:
        """
        Analyze overall cache performance

        Returns:
            Performance metrics and statistics
        """
        total_prompts = len(self.prompts)
        total_usage = sum(p.usage_count for p in self.prompts.values())

        # Calculate average cache hit rates
        static_hits = []
        role_hits = []

        for prompt in self.prompts.values():
            if prompt.tier == CacheTier.STATIC_PREFIX:
                static_hits.append(self._estimate_cache_hit_rate(prompt))
            elif prompt.tier == CacheTier.ROLE_SPECIFIC:
                role_hits.append(self._estimate_cache_hit_rate(prompt))

        avg_static_hit = sum(static_hits) / len(static_hits) if static_hits else 0
        avg_role_hit = sum(role_hits) / len(role_hits) if role_hits else 0

        # Recent updates
        recent_updates = [h for h in self.history if h.success][-10:]

        return {
            "total_cached_prompts": total_prompts,
            "total_usage_count": total_usage,
            "average_static_cache_hit": avg_static_hit,
            "average_role_cache_hit": avg_role_hit,
            "recent_updates": recent_updates,
            "cache_size_mb": self._get_cache_size()
        }

    # ========== Private Methods ==========

    def _get_cache_file(self, domain: str, role: str, tier: CacheTier) -> Path:
        """Get cache file path for a prompt"""
        filename = f"{domain}_{role}.json"
        return self.cache_dir / tier.value / filename

    def _save_cached_prompt(self, prompt: CachedPrompt) -> None:
        """Save cached prompt to disk"""
        cache_file = self._get_cache_file(prompt.domain, prompt.role, prompt.tier)

        # Convert to dict and handle enum serialization
        prompt_dict = asdict(prompt)
        prompt_dict['tier'] = prompt.tier.value  # Convert enum to string

        with open(cache_file, 'w') as f:
            json.dump(prompt_dict, f, indent=2)

    def _estimate_cache_hit_rate(self, prompt: CachedPrompt) -> float:
        """Estimate cache hit rate based on prompt structure"""
        if not prompt:
            return 0.0

        content = prompt.content
        lines = content.split('\n')

        # Count static vs dynamic markers
        static_markers = [
            '<role_definition>', '<core_protocol>', '<workflow_structure>',
            '<tool_specifications>', '<immutable_rules>', '<error_prevention>'
        ]

        dynamic_markers = [
            '<current_task>', '<observation>', '<action_history>',
            '<dynamic_examples>'
        ]

        static_lines = sum(1 for line in lines if any(m in line for m in static_markers))
        dynamic_lines = sum(1 for line in lines if any(m in line for m in dynamic_markers))

        total_lines = len(lines)
        if total_lines == 0:
            return 0.0

        static_ratio = static_lines / total_lines

        # Map ratio to cache hit rate
        if prompt.tier == CacheTier.STATIC_PREFIX:
            return min(0.95, static_ratio * 1.2)  # Max 95%
        elif prompt.tier == CacheTier.ROLE_SPECIFIC:
            return min(0.70, static_ratio * 1.0)  # Max 70%
        else:  # DYNAMIC
            return 0.0

    def _estimate_token_savings(
        self,
        old_prompt: Optional[CachedPrompt],
        new_prompt: CachedPrompt
    ) -> int:
        """Estimate token savings from cache hits"""
        if not old_prompt:
            return 0

        # Rough estimate: 4 chars per token
        old_size = len(old_prompt.content) // 4
        new_size = len(new_prompt.content) // 4

        # Assume better cache hit rate = more savings
        old_hit = self._estimate_cache_hit_rate(old_prompt)
        new_hit = self._estimate_cache_hit_rate(new_prompt)

        # Savings = (new_hit - old_hit) * new_size
        return int((new_hit - old_hit) * new_size)

    def _analyze_changes(
        self,
        old_prompt: Optional[CachedPrompt],
        new_prompt: CachedPrompt
    ) -> List[str]:
        """Analyze what changed between prompt versions"""
        changes = []

        if not old_prompt:
            return ["Initial version"]

        old_len = len(old_prompt.content)
        new_len = len(new_prompt.content)

        if new_len > old_len:
            changes.append(f"Expanded prompt by {new_len - old_len} chars")
        elif new_len < old_len:
            changes.append(f"Compressed prompt by {old_len - new_len} chars")

        # Check for new sections
        for section in ['<tool_specifications>', '<error_prevention>', '<workflow_structure>']:
            if section in new_prompt.content and section not in old_prompt.content:
                changes.append(f"Added {section}")

        return changes

    def _needs_optimization(self, prompt: CachedPrompt) -> bool:
        """Check if prompt needs optimization based on performance"""
        # Check if cache hit rate is below threshold
        hit_rate = self._estimate_cache_hit_rate(prompt)

        if prompt.tier == CacheTier.STATIC_PREFIX and hit_rate < 0.70:
            return True
        if prompt.tier == CacheTier.ROLE_SPECIFIC and hit_rate < 0.40:
            return True

        return False

    def _generate_default_static_prefix(self, domain: str) -> str:
        """Generate default static prefix for a domain"""
        return f"""<role_definition>
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

    def _generate_static_prefix(self, agent) -> str:
        """Generate static prefix for an agent (placeholder for LLM-based generation)"""
        # This will be replaced with LLM-based generation
        return self._generate_default_static_prefix(agent.domain)

    def _generate_role_specific(self, agent) -> str:
        """Generate role-specific prompt (placeholder for LLM-based generation)"""
        return f"""<role_specific>
## {agent.role.capitalize()} Instructions

As a {agent.role}, your primary responsibility is:
{agent.metadata.get('responsibility', 'Complete tasks efficiently')}

### Coordination
- Collaborate with other agents when needed
- Report progress and failures clearly
- Follow escalation procedures for complex issues
</role_specific>
"""

    def _build_dynamic_content(
        self,
        agent,
        task_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build dynamic content for current task"""
        parts = ["<current_task>", ""]

        if task_context:
            if "task_description" in task_context:
                parts.append(f"## Task")
                parts.append(task_context["task_description"])
                parts.append("")

            if "observation" in task_context:
                parts.append(f"## Current Observation")
                parts.append(task_context["observation"])
                parts.append("")

            if "action_history" in task_context:
                parts.append(f"## Recent Actions")
                for action in task_context["action_history"][-5:]:
                    parts.append(f"- {action}")
                parts.append("")

        parts.append("</current_task>")

        return "\n".join(parts)

    def _calculate_cache_hit_potential(
        self,
        static_chars: int,
        role_chars: int,
        dynamic_chars: int
    ) -> Dict[str, Any]:
        """Calculate cache hit potential"""
        total_chars = static_chars + role_chars + dynamic_chars

        if total_chars == 0:
            return {"potential": "none", "ratio": 0.0}

        static_ratio = static_chars / total_chars
        combined_static = (static_chars + role_chars) / total_chars

        if static_ratio >= 0.70:
            potential = "high"
        elif combined_static >= 0.60:
            potential = "medium"
        else:
            potential = "low"

        return {
            "potential": potential,
            "static_ratio": static_ratio,
            "combined_static_ratio": combined_static
        }

    def _get_cache_size(self) -> float:
        """Get total cache size in MB"""
        total_size = 0
        for cache_file in self.cache_dir.rglob("*.json"):
            total_size += cache_file.stat().st_size
        return total_size / (1024 * 1024)


# Singleton instance
_cache_manager_instance: Optional[PromptCacheManager] = None


def get_prompt_cache_manager() -> PromptCacheManager:
    """Get singleton prompt cache manager instance"""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = PromptCacheManager()
    return _cache_manager_instance
