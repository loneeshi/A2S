"""
Reflection Agent for Auto-Expansion Agent Cluster

Analyzes task failures (LLM-driven with rule-based fallback) and applies
structured prompt updates via the prompt cache system.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .schema import ReflectionTrigger, PromptUpdateAction, ReflectionOutput
from core.prompts.cache_manager import CacheTier, get_prompt_cache_manager

logger = logging.getLogger(__name__)

ACTION_TO_SECTION = {
    PromptUpdateAction.UPDATE_ERROR_PREVENTION: "error_prevention",
    PromptUpdateAction.UPDATE_TOOL_SPECIFICATIONS: "tool_specifications",
    PromptUpdateAction.UPDATE_CORE_PROTOCOL: "core_protocol",
    PromptUpdateAction.UPDATE_WORKFLOW_STRUCTURE: "workflow_structure",
    PromptUpdateAction.ADD_DYNAMIC_EXAMPLE: "dynamic_examples",
}

ACTION_TO_TIER = {
    PromptUpdateAction.UPDATE_ERROR_PREVENTION: CacheTier.STATIC_PREFIX,
    PromptUpdateAction.UPDATE_TOOL_SPECIFICATIONS: CacheTier.STATIC_PREFIX,
    PromptUpdateAction.UPDATE_CORE_PROTOCOL: CacheTier.STATIC_PREFIX,
    PromptUpdateAction.UPDATE_WORKFLOW_STRUCTURE: CacheTier.STATIC_PREFIX,
    PromptUpdateAction.ADD_DYNAMIC_EXAMPLE: CacheTier.DYNAMIC,
}


class ReflectionAgent:
    """
    Analyzes task failures and produces structured ReflectionOutput.

    Uses LLM-driven analysis when available, falling back to rule-based
    heuristics. Applies prompt updates through the prompt cache system.
    """

    def analyze_failure(self, failure_info: Dict) -> ReflectionOutput:
        """
        Analyze a single task failure and produce structured reflection.

        Args:
            failure_info: Dict with keys: domain, task_type, agent_name,
                episode_id (optional), error_message, action_history,
                observation, tools_used, success_rate

        Returns:
            ReflectionOutput with analysis and recommendations
        """
        reflection_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        try:
            return self._analyze_with_llm(failure_info, reflection_id, timestamp)
        except Exception as exc:
            logger.warning(f"LLM analysis failed ({exc}), using rule-based fallback")
            return self._analyze_rule_based(failure_info, reflection_id, timestamp)

    def analyze_batch(self, failures: List[Dict]) -> List[ReflectionOutput]:
        """
        Analyze a batch of failures.

        Args:
            failures: List of failure_info dicts

        Returns:
            List of ReflectionOutput, one per failure
        """
        return [self.analyze_failure(f) for f in failures]

    def apply_prompt_updates(self, reflections: List[ReflectionOutput]) -> List[Dict]:
        """
        Apply prompt updates from reflections to the prompt cache.

        Args:
            reflections: List of ReflectionOutput with prompt update recommendations

        Returns:
            List of result dicts with keys: reflection_id, domain, action, tier, success
        """
        cache = get_prompt_cache_manager()
        results = []

        for reflection in reflections:
            if reflection.prompt_update_action == PromptUpdateAction.NO_UPDATE:
                continue

            action = reflection.prompt_update_action
            tier = ACTION_TO_TIER[action]
            section_tag = ACTION_TO_SECTION[action]

            try:
                cached = cache.get_cached_prompt(reflection.domain, "worker", tier)

                if cached:
                    content = self._inject_into_section(
                        cached.content, section_tag, reflection.prompt_update_content
                    )
                else:
                    content = (
                        f"<{section_tag}>\n"
                        f"{reflection.prompt_update_content}\n"
                        f"</{section_tag}>"
                    )

                cache.update_cached_prompt(
                    domain=reflection.domain,
                    role="worker",
                    tier=tier,
                    content=content,
                    update_reason=f"reflection:{reflection.reflection_id}",
                    metadata={
                        "reflection_id": reflection.reflection_id,
                        "action": action.value,
                    },
                )

                results.append(
                    {
                        "reflection_id": reflection.reflection_id,
                        "domain": reflection.domain,
                        "action": action.value,
                        "tier": tier.value,
                        "success": True,
                    }
                )

            except Exception as exc:
                logger.error(
                    f"Failed to apply prompt update for {reflection.reflection_id}: {exc}"
                )
                results.append(
                    {
                        "reflection_id": reflection.reflection_id,
                        "domain": reflection.domain,
                        "action": action.value,
                        "tier": tier.value,
                        "success": False,
                    }
                )

        return results

    # ========== Private Methods ==========

    def _call_llm(self, prompt: str) -> str:
        """
        Call the project LLM client with a prompt.

        Args:
            prompt: Input prompt string

        Returns:
            Response content string

        Raises:
            Exception: If LLM client is unavailable or call fails
        """
        from core.llm.client import LLMClient

        client = LLMClient()
        response = client.complete(prompt=prompt, temperature=0.3)
        return response.content

    def _analyze_with_llm(
        self, failure_info: Dict, reflection_id: str, timestamp: str
    ) -> ReflectionOutput:
        """Run LLM-driven failure analysis."""
        prompt = self._build_analysis_prompt(failure_info)
        raw = self._call_llm(prompt)

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]

        data = json.loads(raw)

        return ReflectionOutput(
            reflection_id=reflection_id,
            timestamp=timestamp,
            trigger=ReflectionTrigger.TASK_FAILURE,
            domain=failure_info["domain"],
            task_type=failure_info["task_type"],
            agent_name=failure_info["agent_name"],
            episode_id=failure_info.get("episode_id"),
            failure_type=data.get("failure_type", "unknown"),
            root_cause=data.get("root_cause", ""),
            tools_involved=data.get(
                "tools_involved", failure_info.get("tools_used", [])
            ),
            error_pattern=data.get("error_pattern", ""),
            prompt_update_action=PromptUpdateAction(
                data.get("prompt_update_action", "no_update")
            ),
            prompt_update_content=data.get("prompt_update_content", ""),
            memory_updates=data.get("memory_updates", []),
            retry_recommendation=data.get("retry_recommendation", False),
            confidence=float(data.get("confidence", 0.5)),
            success_rate_before=failure_info.get("success_rate", 0.0),
            total_failures_analyzed=1,
        )

    def _analyze_rule_based(
        self, failure_info: Dict, reflection_id: str, timestamp: str
    ) -> ReflectionOutput:
        """Rule-based fallback when LLM is unavailable."""
        error = failure_info.get("error_message", "").lower()

        if "tool" in error or "function" in error:
            failure_type = "tool_misuse"
            action = PromptUpdateAction.UPDATE_TOOL_SPECIFICATIONS
        elif "step" in error or "sequence" in error or "order" in error:
            failure_type = "missing_step"
            action = PromptUpdateAction.UPDATE_WORKFLOW_STRUCTURE
        elif "object" in error or "target" in error or "wrong" in error:
            failure_type = "wrong_object"
            action = PromptUpdateAction.UPDATE_ERROR_PREVENTION
        else:
            failure_type = "unknown"
            action = PromptUpdateAction.NO_UPDATE

        domain = failure_info["domain"]
        error_pattern = f"{failure_type}:{domain}"

        prompt_update_content = ""
        if action != PromptUpdateAction.NO_UPDATE:
            prompt_update_content = (
                f"[Auto-detected {failure_type}] "
                f"Error: {failure_info.get('error_message', 'N/A')}. "
                f"Tools involved: {', '.join(failure_info.get('tools_used', []))}."
            )

        return ReflectionOutput(
            reflection_id=reflection_id,
            timestamp=timestamp,
            trigger=ReflectionTrigger.TASK_FAILURE,
            domain=domain,
            task_type=failure_info["task_type"],
            agent_name=failure_info["agent_name"],
            episode_id=failure_info.get("episode_id"),
            failure_type=failure_type,
            root_cause=failure_info.get("error_message", ""),
            tools_involved=failure_info.get("tools_used", []),
            error_pattern=error_pattern,
            prompt_update_action=action,
            prompt_update_content=prompt_update_content,
            memory_updates=[],
            retry_recommendation=action != PromptUpdateAction.NO_UPDATE,
            confidence=0.3,
            success_rate_before=failure_info.get("success_rate", 0.0),
            total_failures_analyzed=1,
        )

    def _build_analysis_prompt(self, failure_info: Dict) -> str:
        """Build the LLM prompt for failure analysis."""
        actions_str = "\n".join(
            f"  - {a}" for a in failure_info.get("action_history", [])
        )
        tools_str = ", ".join(failure_info.get("tools_used", []))

        return f"""Analyze this agent task failure and return a JSON object.

Domain: {failure_info["domain"]}
Task type: {failure_info["task_type"]}
Agent: {failure_info["agent_name"]}
Error message: {failure_info.get("error_message", "N/A")}
Observation: {failure_info.get("observation", "N/A")}
Tools used: {tools_str}
Success rate: {failure_info.get("success_rate", 0.0)}
Action history:
{actions_str}

Return ONLY a JSON object with these fields:
- failure_type: one of "wrong_object", "missing_step", "tool_misuse", "incorrect_sequence", "unknown"
- root_cause: 1-2 sentence root cause
- tools_involved: list of tool names involved in the failure
- error_pattern: short pattern name for deduplication (e.g. "tool_misuse:navigation")
- prompt_update_action: one of "update_error_prevention", "update_tool_specifications", "update_core_protocol", "update_workflow_structure", "add_dynamic_example", "no_update"
- prompt_update_content: specific text to add to the prompt section
- memory_updates: list of objects with "type" ("lesson"|"error_pattern"|"tool_tip"), "content", and "tags"
- retry_recommendation: boolean
- confidence: float 0.0-1.0
"""

    def _inject_into_section(
        self, content: str, section_tag: str, update_content: str
    ) -> str:
        """Inject update content into an existing XML section of a cached prompt."""
        closing_tag = f"</{section_tag}>"
        if closing_tag in content:
            return content.replace(
                closing_tag,
                f"{update_content}\n{closing_tag}",
            )

        return f"{content}\n\n<{section_tag}>\n{update_content}\n</{section_tag}>"


_reflection_agent_instance: Optional[ReflectionAgent] = None


def get_reflection_agent() -> ReflectionAgent:
    """Get singleton ReflectionAgent instance."""
    global _reflection_agent_instance
    if _reflection_agent_instance is None:
        _reflection_agent_instance = ReflectionAgent()
    return _reflection_agent_instance
