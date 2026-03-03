"""
LLM-Driven Prompt Optimizer for Auto-Expansion Agent Cluster

This module uses LLM to analyze performance data and optimize prompts
while maintaining cache-friendly structure.

Usage:
    optimizer = PromptOptimizer(llm_client)
    optimized_prompt = optimizer.optimize_static_prefix(
        domain="manipulation",
        current_prompt=current_prompt,
        performance_data=performance_metrics
    )
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .cache_manager import CacheTier, CachedPrompt

logger = logging.getLogger(__name__)


@dataclass
class OptimizationSuggestion:
    """Suggestion for prompt optimization"""
    section: str  # Which section to modify
    issue: str    # What the problem is
    suggestion: str  # What to change
    priority: str  # "high" | "medium" | "low"
    expected_improvement: str  # Description of expected benefit


@dataclass
class OptimizationResult:
    """Result of prompt optimization"""
    original_prompt: str
    optimized_prompt: str
    suggestions: List[OptimizationSuggestion]
    token_reduction: int
    cache_hit_improvement: float
    reasoning: str  # Why changes were made


class PromptOptimizer:
    """
    Use LLM to optimize prompts for better cache hit rates and performance

    Key capabilities:
    1. Analyze failure patterns from task results
    2. Identify missing instructions or unclear guidelines
    3. Suggest improvements to prompt structure
    4. Generate optimized prompts while maintaining cache-friendly structure
    5. Validate that optimized prompts meet caching requirements
    """

    def __init__(self, llm_client=None):
        """
        Initialize prompt optimizer

        Args:
            llm_client: LLM client for generating optimizations
        """
        self.llm_client = llm_client
        logger.info("PromptOptimizer initialized")

    def optimize_static_prefix(
        self,
        domain: str,
        current_prompt: str,
        performance_data: Optional[Dict[str, Any]] = None
    ) -> OptimizationResult:
        """
        Optimize static prefix for a domain

        Args:
            domain: Agent domain (e.g., "manipulation", "navigation")
            current_prompt: Current static prefix content
            performance_data: Performance metrics and failure patterns

        Returns:
            OptimizationResult with optimized prompt and changes
        """
        logger.info(f"Optimizing static prefix for domain: {domain}")

        # Analyze current prompt
        current_analysis = self._analyze_prompt_structure(current_prompt)

        # Generate optimization suggestions (using LLM if available)
        if self.llm_client:
            suggestions = self._generate_llm_suggestions(
                domain, current_prompt, performance_data
            )
        else:
            suggestions = self._generate_rule_based_suggestions(
                domain, current_prompt, current_analysis, performance_data
            )

        # Apply optimizations
        optimized_prompt = self._apply_optimizations(current_prompt, suggestions)

        # Calculate improvements
        token_reduction = len(current_prompt) - len(optimized_prompt)
        cache_improvement = self._estimate_cache_improvement(
            current_prompt, optimized_prompt
        )

        result = OptimizationResult(
            original_prompt=current_prompt,
            optimized_prompt=optimized_prompt,
            suggestions=suggestions,
            token_reduction=token_reduction,
            cache_hit_improvement=cache_improvement,
            reasoning=f"Optimized based on {len(suggestions)} suggestions"
        )

        logger.info(
            f"Optimization complete: "
            f"token_reduction={token_reduction}, "
            f"cache_improvement={cache_improvement:.1%}"
        )

        return result

    def generate_static_prefix_from_tasks(
        self,
        domain: str,
        task_examples: List[Dict[str, Any]],
        tools: List[str]
    ) -> str:
        """
        Generate a new static prefix from task examples using LLM

        Args:
            domain: Agent domain
            task_examples: List of successful and failed tasks
            tools: List of available tools

        Returns:
            Generated static prefix prompt
        """
        if not self.llm_client:
            logger.warning("No LLM client available, using default template")
            return self._generate_default_template(domain, tools)

        # Build prompt for LLM
        llm_prompt = self._build_generation_prompt(domain, task_examples, tools)

        try:
            response = self.llm_client.complete(
                prompt=llm_prompt,
                temperature=0.3,  # Lower temperature for consistent output
                max_tokens=2000
            )

            # Validate and clean generated prompt
            cleaned_prompt = self._validate_and_clean(response.content)

            return cleaned_prompt

        except Exception as e:
            logger.error(f"LLM generation failed: {e}, using default template")
            return self._generate_default_template(domain, tools)

    def optimize_after_extension(
        self,
        new_agents: List[Any],
        performance_history: List[Any]
    ) -> List[OptimizationResult]:
        """
        Optimize prompts after agent tree extension

        This is called automatically when new agents are added to optimize
        prompts for both new and existing agents based on performance data.

        Args:
            new_agents: List of newly added agents
            performance_history: Recent task performance data

        Returns:
            List of optimization results for each affected domain
        """
        results = []

        # Group new agents by domain
        domains_to_update = {}
        for agent in new_agents:
            domain = agent.metadata.get("prompt_builder_domain", agent.domain)
            if domain not in domains_to_update:
                domains_to_update[domain] = []
            domains_to_update[domain].append(agent)

        # Optimize each domain
        for domain, agents in domains_to_update.items():
            # Extract performance data for this domain
            domain_performance = self._extract_domain_performance(
                domain, performance_history
            )

            # Get current static prefix (if any)
            current_prompt = self._get_current_prompt(domain)

            # Optimize
            result = self.optimize_static_prefix(
                domain=domain,
                current_prompt=current_prompt,
                performance_data=domain_performance
            )

            results.append(result)

        return results

    # ========== Private Methods ==========

    def _analyze_prompt_structure(self, prompt: str) -> Dict[str, Any]:
        """Analyze the structure of a prompt"""
        lines = prompt.split('\n')

        sections = {}
        current_section = None

        for line in lines:
            if line.strip().startswith('<') and line.strip().endswith('>'):
                current_section = line.strip()
                sections[current_section] = []
            elif current_section:
                sections[current_section].append(line)

        return {
            "sections": list(sections.keys()),
            "line_count": len(lines),
            "char_count": len(prompt),
            "estimated_tokens": len(prompt) // 4
        }

    def _generate_llm_suggestions(
        self,
        domain: str,
        current_prompt: str,
        performance_data: Optional[Dict[str, Any]]
    ) -> List[OptimizationSuggestion]:
        """Generate optimization suggestions using LLM"""
        llm_prompt = f"""Analyze this {domain} agent prompt and suggest improvements for better performance and cache hit rate:

CURRENT PROMPT:
{current_prompt}

{'PERFORMANCE DATA:' + str(performance_data) if performance_data else 'NO PERFORMANCE DATA'}

Provide 3-5 specific suggestions in this format:
SUGGESTION 1:
- Section: <section_name>
- Issue: <what's wrong>
- Suggestion: <how to fix>
- Priority: <high|medium|low>
- Expected: <expected benefit>

Focus on:
1. Clarity of instructions
2. Cache-friendly structure (static content first)
3. Missing error cases
4. Tool usage guidelines
5. Common failure patterns
"""

        try:
            response = self.llm_client.complete(
                prompt=llm_prompt,
                temperature=0.5,
                max_tokens=1500
            )

            # Parse suggestions from LLM response
            suggestions = self._parse_suggestions(response.content)
            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate LLM suggestions: {e}")
            return []

    def _generate_rule_based_suggestions(
        self,
        domain: str,
        prompt: str,
        analysis: Dict[str, Any],
        performance_data: Optional[Dict[str, Any]]
    ) -> List[OptimizationSuggestion]:
        """Generate rule-based optimization suggestions"""
        suggestions = []

        # Check for missing sections
        required_sections = [
            '<role_definition>',
            '<core_protocol>',
            '<tool_specifications>',
            '<error_prevention>'
        ]

        for section in required_sections:
            if section not in str(analysis.get("sections", [])):
                suggestions.append(OptimizationSuggestion(
                    section=section,
                    issue=f"Missing {section} section",
                    suggestion=f"Add {section} with clear guidelines",
                    priority="high",
                    expected_improvement="Better agent behavior"
                ))

        # Check prompt length
        token_count = analysis.get("estimated_tokens", 0)
        if token_count < 800:
            suggestions.append(OptimizationSuggestion(
                section="overall",
                issue="Static prefix too short for good cache hits",
                suggestion="Expand to at least 1000-1200 tokens",
                priority="high",
                expected_improvement="70-80% cache hit rate"
            ))

        # Check for error prevention patterns
        if '<error_prevention>' not in prompt:
            suggestions.append(OptimizationSuggestion(
                section="error_prevention",
                issue="No error prevention guidelines",
                suggestion="Add common error patterns and how to avoid them",
                priority="medium",
                expected_improvement="Fewer failures"
            ))

        return suggestions

    def _apply_optimizations(
        self,
        prompt: str,
        suggestions: List[OptimizationSuggestion]
    ) -> str:
        """Apply optimization suggestions to prompt"""
        # For now, return original prompt
        # In production, this would intelligently apply suggestions
        # TODO: Implement suggestion application logic
        return prompt

    def _estimate_cache_improvement(
        self,
        original: str,
        optimized: str
    ) -> float:
        """Estimate improvement in cache hit rate"""
        # Simple heuristic: longer static prefix = better cache hit
        original_len = len(original)
        optimized_len = len(optimized)

        if original_len == 0:
            return 0.0

        # Assume diminishing returns after 1500 chars
        improvement = min(0.2, (optimized_len - original_len) / 5000)
        return max(-0.1, improvement)  # Cap at -10% to +20%

    def _build_generation_prompt(
        self,
        domain: str,
        task_examples: List[Dict[str, Any]],
        tools: List[str]
    ) -> str:
        """Build prompt for LLM to generate static prefix"""
        return f"""Generate a cache-optimized static prefix for {domain} agents in an ALFWorld benchmark.

DOMAIN: {domain}
TOOLS: {', '.join(tools)}

TASK EXAMPLES:
{self._format_task_examples(task_examples)}

REQUIREMENTS:
1. Generate a comprehensive static prefix (~1200 tokens)
2. Structure for prompt caching (static content first)
3. Include these sections:
   - <role_definition>: What this agent does
   - <core_protocol>: Immutable rules
   - <workflow_structure>: Standard workflow phases
   - <tool_specifications>: Each tool with usage examples
   - <error_prevention>: Common errors and how to avoid them

4. Make it specific to {domain} tasks
5. Include concrete examples
6. Focus on patterns that prevent failures

Generate the static prefix now:"""

    def _format_task_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format task examples for LLM prompt"""
        formatted = []
        for i, example in enumerate(examples[:5], 1):  # Limit to 5 examples
            status = "✓ Success" if example.get("success") else "✗ Failure"
            formatted.append(f"Example {i} {status}:")
            formatted.append(f"  Task: {example.get('task', 'N/A')}")
            if example.get("error"):
                formatted.append(f"  Error: {example['error']}")
            formatted.append("")

        return "\n".join(formatted)

    def _validate_and_clean(self, prompt: str) -> str:
        """Validate and clean generated prompt"""
        # Remove markdown code blocks if present
        if prompt.startswith("```"):
            prompt = "\n".join(prompt.split("\n")[1:-1])

        # Ensure it has required sections
        required = ["<role_definition>", "<core_protocol>"]
        for section in required:
            if section not in prompt:
                logger.warning(f"Generated prompt missing {section}")

        return prompt.strip()

    def _generate_default_template(self, domain: str, tools: List[str]) -> str:
        """Generate default template when LLM is unavailable"""
        return f"""<role_definition>
You are a {domain} specialist in the ALFWorld environment.
Your role is to accomplish {domain} tasks efficiently and correctly.
</role_definition>

<core_protocol>
## {domain.capitalize()} Protocol (v1.0)

### Immutable Rules
1. Always observe the environment before acting
2. Use tools correctly with proper parameters
3. Verify results before proceeding
4. Report failures clearly with context
5. Never make assumptions about object locations
</core_protocol>

<workflow_structure>
## Standard {domain.capitalize()} Workflow

### Phase 1: Observe
- Look around the current location
- Note objects, containers, and their states
- Identify task-relevant items

### Phase 2: Plan
- Determine sequence of actions needed
- Identify required tools for each step
- Plan for potential obstacles

### Phase 3: Execute
- Perform actions in correct order
- Verify each action's result
- Handle unexpected situations

### Phase 4: Verify
- Confirm task completion
- Check all requirements met
- Report final status
</workflow_structure>

<tool_specifications>
## Available Tools

{self._format_tools(tools)}
</tool_specifications>

<error_prevention>
## Common {domain.capitalize()} Errors

### Error 1: Acting Without Observation
❌ WRONG: Take action without looking around first
✅ CORRECT: Always observe environment before acting

### Error 2: Ignoring Object States
❌ WRONG: Assume objects are in default state
✅ CORRECT: Check object state before interacting

### Error 3: Incorrect Tool Usage
❌ WRONG: Use wrong tool for the task
✅ CORRECT: Match tool to specific requirement

### Error 4: Incomplete Verification
❌ WRONG: Assume task is done without checking
✅ CORRECT: Verify all requirements are satisfied
</error_prevention>
"""

    def _format_tools(self, tools: List[str]) -> str:
        """Format tools for prompt"""
        formatted = []
        for tool in tools:
            formatted.append(f"### {tool}")
            formatted.append(f"**Purpose**: [To be documented]")
            formatted.append(f"**Usage**: `{tool}(...parameters...)`")
            formatted.append("")
        return "\n".join(formatted)

    def _extract_domain_performance(
        self,
        domain: str,
        performance_history: List[Any]
    ) -> Dict[str, Any]:
        """Extract performance data for a specific domain"""
        # Filter tasks related to this domain
        domain_tasks = [
            p for p in performance_history
            if p.metadata.get("domain") == domain
        ]

        if not domain_tasks:
            return {}

        # Calculate metrics
        success_rate = sum(1 for t in domain_tasks if t.status == "SUCCESS") / len(domain_tasks)
        common_errors = {}

        for task in domain_tasks:
            if task.error_message:
                common_errors[task.error_message] = common_errors.get(task.error_message, 0) + 1

        return {
            "domain": domain,
            "total_tasks": len(domain_tasks),
            "success_rate": success_rate,
            "common_errors": sorted(common_errors.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    def _get_current_prompt(self, domain: str) -> str:
        """Get current static prefix for a domain"""
        # This would integrate with PromptCacheManager
        from .cache_manager import get_prompt_cache_manager

        manager = get_prompt_cache_manager()
        cached = manager.get_cached_prompt(domain, "worker", CacheTier.STATIC_PREFIX)

        return cached.content if cached else ""

    def _parse_suggestions(self, llm_response: str) -> List[OptimizationSuggestion]:
        """Parse suggestions from LLM response"""
        # Parse the structured response
        # This is a simplified version - production would be more robust
        suggestions = []

        lines = llm_response.split('\n')
        current_suggestion = None

        for line in lines:
            line = line.strip()
            if line.startswith("SUGGESTION"):
                if current_suggestion:
                    suggestions.append(current_suggestion)
                current_suggestion = None
            elif line.startswith("- Section:"):
                if current_suggestion is None:
                    current_suggestion = OptimizationSuggestion(
                        section="", issue="", suggestion="", priority="medium", expected_improvement=""
                    )
                current_suggestion.section = line.split(":", 1)[1].strip()
            elif line.startswith("- Issue:") and current_suggestion:
                current_suggestion.issue = line.split(":", 1)[1].strip()
            elif line.startswith("- Suggestion:") and current_suggestion:
                current_suggestion.suggestion = line.split(":", 1)[1].strip()
            elif line.startswith("- Priority:") and current_suggestion:
                current_suggestion.priority = line.split(":", 1)[1].strip().lower()
            elif line.startswith("- Expected:") and current_suggestion:
                current_suggestion.expected_improvement = line.split(":", 1)[1].strip()

        if current_suggestion:
            suggestions.append(current_suggestion)

        return suggestions
