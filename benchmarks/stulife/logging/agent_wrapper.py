"""
Tracked StuLife Agent - Wrapper for logging API calls and worker actions

Wraps the StuLifeAgent to intercept API calls and log them to the
three-tier logging system without modifying core/ code.
"""

import logging
import time
from typing import Optional, Dict, List, Any

from core.llm.client import StuLifeAgent, LLMClient, LLMResponse
from .coordinator import LoggingCoordinator
from .context import get_logging_context

logger = logging.getLogger(__name__)


class TrackedStuLifeAgent(StuLifeAgent):
    """
    StuLife agent with integrated three-tier logging

    Wraps select_action() and LLM calls to log:
    - Worker behavior (Tier 2)
    - API calls with full context (Tier 3)
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: Optional[str] = None,
        coordinator: Optional[LoggingCoordinator] = None,
    ):
        """
        Initialize tracked agent

        Args:
            llm_client: LLM client instance
            model: Model to use
            coordinator: Logging coordinator for three-tier logging
        """
        super().__init__(llm_client=llm_client, model=model)
        self.coordinator = coordinator

        # Wrap the LLM client's complete method
        if self.coordinator and self.llm:
            self._wrap_llm_complete()

        logger.info("TrackedStuLifeAgent initialized with logging")

    def _wrap_llm_complete(self):
        """Wrap LLM client's complete method to trace API calls"""
        original_complete = self.llm.complete

        def traced_complete(
            prompt: str,
            model: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            **kwargs,
        ) -> LLMResponse:
            """Wrapped complete method with API tracing"""
            start_time = time.time()

            # Build request data
            request_data = {
                "model": model or self.llm.default_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            request_data.update(kwargs)

            try:
                # Call original method
                response = original_complete(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Calculate latency
                latency_ms = (time.time() - start_time) * 1000

                # Build response data
                response_data = {
                    "content": response.content,
                    "finish_reason": "stop",  # Default
                }

                if response.tool_calls:
                    response_data["tool_calls"] = response.tool_calls

                # Extract usage information
                usage = response.usage or {}

                # Extract cache information if available
                cache_info = {}
                if "prompt_tokens_details" in usage:
                    details = usage["prompt_tokens_details"]
                    if isinstance(details, dict):
                        cache_info["cache_read_input_tokens"] = details.get(
                            "cached_tokens", 0
                        )
                        cache_info["cache_creation_input_tokens"] = 0

                # Trace the call
                if self.coordinator:
                    self.coordinator.trace_api_call(
                        request=request_data,
                        response=response_data,
                        usage=usage,
                        cache_info=cache_info,
                        latency_ms=latency_ms,
                        error=None,
                    )

                return response

            except Exception as e:
                # Log error
                latency_ms = (time.time() - start_time) * 1000

                if self.coordinator:
                    self.coordinator.trace_api_call(
                        request=request_data,
                        response={},
                        usage={},
                        cache_info={},
                        latency_ms=latency_ms,
                        error=str(e),
                    )

                raise

        # Replace the method
        self.llm.complete = traced_complete

    def select_action(
        self,
        observation: str,
        task_description: str,
        max_history_turns: int = 10,
    ) -> str:
        """
        Select action with worker behavior logging

        Args:
            observation: Current observation
            task_description: Task description
            max_history_turns: Max history turns to keep

        Returns:
            Selected action string
        """
        start_time = time.time()

        # Call parent method
        action = super().select_action(
            observation=observation,
            task_description=task_description,
            max_history_turns=max_history_turns,
        )

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log worker action
        if self.coordinator:
            # Extract decision rationale from action (simple heuristic)
            decision_rationale = self._extract_rationale(action)

            self.coordinator.log_worker_action(
                task_summary=task_description[:100],
                action_taken=action[:200],
                decision_rationale=decision_rationale,
                tools_used=[],
                duration_ms=duration_ms,
            )

        return action

    def _extract_rationale(self, action: str) -> str:
        """
        Extract decision rationale from action text

        Simple heuristic: look for reasoning keywords
        """
        # Look for common reasoning patterns
        reasoning_keywords = [
            "because",
            "since",
            "therefore",
            "so that",
            "in order to",
            "to",
        ]

        action_lower = action.lower()
        for keyword in reasoning_keywords:
            if keyword in action_lower:
                # Extract text after keyword
                idx = action_lower.find(keyword)
                rationale = action[idx : idx + 100].strip()
                return rationale

        # Default: use first sentence
        sentences = action.split(".")
        if sentences:
            return sentences[0].strip()

        return "No explicit rationale"
