"""
LLM Client Module for Auto-Expansion Agent Cluster

This module provides a unified interface for calling various LLM APIs.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to load .env file
try:
    from dotenv import load_dotenv

    # Load .env from project root
    project_root = Path(__file__).parent.parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        logger.info(f"Loaded environment variables from {env_file}")
except ImportError:
    # python-dotenv not installed, that's ok
    logger.debug("python-dotenv not available, using environment variables directly")
    pass


@dataclass
class LLMResponse:
    """Response from LLM API"""

    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Any] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None  # Tool calls from response


class LLMClient:
    """
    Unified LLM client supporting multiple providers

    Usage:
        client = LLMClient()
        response = client.complete(
            prompt="What is 2+2?",
            model="gemini-2.5-flash"
        )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        """
        Initialize LLM client

        Args:
            api_key: API key (defaults to OPENAI_API_KEY env var)
            base_url: Base URL for API (defaults to OPENAI_BASE_URL env var)
            default_model: Default model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key not found. Please set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.base_url = base_url or os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self.default_model = default_model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")

        # Remove trailing slash from base_url
        self.base_url = self.base_url.rstrip("/")

        self._last_response: Optional[LLMResponse] = None

        logger.info(f"Initialized LLM client with model: {self.default_model}")
        logger.debug(f"Base URL: {self.base_url}")

    def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate completion for a single prompt

        Args:
            prompt: Input prompt
            model: Model to use (defaults to client's default_model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for the API

        Returns:
            LLMResponse with generated content
        """
        model = model or self.default_model

        messages = [{"role": "user", "content": prompt}]

        return self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate chat completion

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to client's default_model)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tools: Optional list of tool definitions (OpenAI format)
            **kwargs: Additional parameters for the API

        Returns:
            LLMResponse with generated content and optional tool_calls
        """
        model = model or self.default_model

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.info(f"🔄 Calling LLM API...")
        logger.info(f"   URL: {url}")
        logger.info(f"   Model: {model}")
        logger.info(f"   Temperature: {temperature}")
        logger.info(f"   Max tokens: {max_tokens or 'default'}")
        if tools:
            logger.info(f"   Tools: {len(tools)} tools provided")
        logger.debug(f"   Messages count: {len(messages)}")
        logger.debug(f"   Payload size: {len(str(payload))} chars")

        try:
            import time

            start_time = time.time()

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,  # Increased timeout to 120 seconds
            )
            response.raise_for_status()

            elapsed_time = time.time() - start_time
            logger.info(f"✅ API call completed in {elapsed_time:.2f}s")

            data = response.json()
            logger.debug(f"   Response status: {response.status_code}")
            logger.debug(f"   Response keys: {list(data.keys())}")

            # Extract content and tool calls
            message = data["choices"][0]["message"]
            content = message.get("content", "")
            tool_calls = message.get("tool_calls")
            usage = data.get("usage", {})

            if tool_calls:
                logger.info(f"   Tool calls: {len(tool_calls)}")

            if usage:
                logger.info(
                    f"   Tokens used: {usage.get('total_tokens', 'N/A')} "
                    f"(prompt: {usage.get('prompt_tokens', 'N/A')}, "
                    f"completion: {usage.get('completion_tokens', 'N/A')})"
                )

            resp = LLMResponse(
                content=content,
                model=model,
                usage=usage,
                raw_response=data,
                tool_calls=tool_calls,
            )
            self._last_response = resp
            return resp

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ LLM API request failed!")
            logger.error(f"   Error type: {type(e).__name__}")
            logger.error(f"   Error message: {str(e)}")

            if hasattr(e, "response") and e.response is not None:
                logger.error(f"   HTTP Status: {e.response.status_code}")
                logger.error(f"   Response headers: {dict(e.response.headers)}")
                logger.error(
                    f"   Response body: {e.response.text[:500]}"
                )  # First 500 chars
            elif hasattr(e, "request") and e.request is not None:
                logger.error(f"   Request URL: {e.request.url}")
                logger.error(f"   Request method: {e.request.method}")
                logger.error(f" Request headers: {dict(e.request.headers)}")
            else:
                logger.error(f"   No additional error info available")

            raise

    def batch_complete(
        self,
        prompts: List[str],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> List[LLMResponse]:
        """
        Generate completions for multiple prompts

        Args:
            prompts: List of input prompts
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            List of LLMResponse objects
        """
        responses = []
        for i, prompt in enumerate(prompts):
            logger.debug(f"Processing prompt {i + 1}/{len(prompts)}")
            response = self.complete(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            responses.append(response)

        return responses


class ALFWorldAgent:
    """
    LLM-powered agent for ALFWorld tasks

    Uses an LLM to select actions based on observations and task goals.
    """

    def __init__(
        self, llm_client: Optional[LLMClient] = None, model: Optional[str] = None
    ):
        """
        Initialize ALFWorld agent

        Args:
            llm_client: LLM client instance (will create default if not provided)
            model: Model to use for action selection
        """
        if llm_client is None:
            llm_client = LLMClient(default_model=model or "gemini-2.5-flash")

        self.llm = llm_client
        self.model = model or llm_client.default_model
        self.conversation_history: List[Dict[str, str]] = []

        logger.info(f"Initialized ALFWorld agent with model: {self.model}")

    def select_action(
        self,
        observation: str,
        task_description: str,
        admissible_actions: List[str],
        max_history_turns: int = 10,
    ) -> str:
        """
        Select an action based on current observation and available actions

        Args:
            observation: Current observation from environment
            task_description: Description of the task to complete
            admissible_actions: List of valid actions (may contain tuples, will be cleaned)
            max_history_turns: Maximum number of conversation turns to keep

        Returns:
            Selected action string

        Raises:
            Exception: If LLM fails to select an action
        """
        # Convert observation to string if it's a tuple
        if isinstance(observation, tuple):
            observation = observation[0] if observation else str(observation)
        if not isinstance(observation, str):
            observation = str(observation)

        # Convert task_description to string if it's a tuple
        if isinstance(task_description, tuple):
            task_description = (
                task_description[0] if task_description else str(task_description)
            )
        if not isinstance(task_description, str):
            task_description = str(task_description)

        # Clean admissible_actions - ensure all are strings
        clean_actions = []
        for action in admissible_actions:
            if isinstance(action, tuple):
                # Extract string from tuple - ensure it's a string
                first_elem = action[0] if len(action) > 0 else None
                if isinstance(first_elem, str):
                    clean_actions.append(first_elem)
                else:
                    clean_actions.append(
                        str(first_elem) if first_elem is not None else "look around"
                    )
            elif isinstance(action, str):
                clean_actions.append(action)
            else:
                clean_actions.append(str(action))

        if not clean_actions:
            clean_actions = ["look around"]

        # Build prompt
        prompt = self._build_action_selection_prompt(
            observation=observation,
            task_description=task_description,
            admissible_actions=clean_actions,
            history=self.conversation_history[-max_history_turns * 2 :],
        )

        try:
            response = self.llm.complete(
                prompt=prompt,
                model=self.model,
                temperature=0.3,  # Lower temperature for more deterministic actions
                max_tokens=500,
            )

            action = self._parse_action(response.content, clean_actions)

            # Update conversation history
            self.conversation_history.append(
                {
                    "role": "user",
                    "content": f"Observation: {observation}\nAvailable actions: {len(clean_actions)} commands",
                }
            )
            self.conversation_history.append(
                {"role": "assistant", "content": f"Action: {action}"}
            )

            return action

        except Exception as e:
            logger.error(f"Failed to get LLM response: {e}")
            # Re-raise exception instead of fallback - let caller handle it
            raise

    def _build_action_selection_prompt(
        self,
        observation: str,
        task_description: str,
        admissible_actions: List[str],
        history: List[Dict[str, str]],
    ) -> str:
        """Build prompt for action selection"""

        prompt_parts = [
            "You are playing an interactive text-based game called ALFWorld.",
            f"Your task: {task_description}",
            "",
            "Current observation:",
            observation,
            "",
            "You must choose ONE action from the following list:",
        ]

        for i, action in enumerate(admissible_actions, 1):
            # Clean action type - handle tuples, strings, etc.
            if isinstance(action, tuple):
                action_str = action[0] if action else str(action)
            elif isinstance(action, str):
                action_str = action
            else:
                action_str = str(action)
            prompt_parts.append(f"{i}. {action_str}")

        prompt_parts.extend(
            [
                "",
                "Rules:",
                "- Choose ONLY from the listed actions",
                "- Respond with just the action text, no explanation",
                "- Think step by step about what will help complete the task",
                "- Be concise and direct",
            ]
        )

        # Add recent history if available
        if history:
            prompt_parts.extend(["", "Recent actions and observations:"])
            for i in range(0, len(history), 2):
                if i + 1 < len(history):
                    user_msg = history[i]["content"]
                    asst_msg = history[i + 1]["content"]
                    prompt_parts.append(f"- {user_msg}")
                    prompt_parts.append(f"  → {asst_msg}")

        prompt_parts.extend(
            ["", "What is your next action? (Respond with just the action text):"]
        )

        return "\n".join(prompt_parts)

    def _parse_action(self, response: str, admissible_actions: List[str]) -> str:
        """
        Parse action from LLM response

        Args:
            response: Raw LLM response text
            admissible_actions: List of valid actions

        Returns:
            Parsed action string
        """
        response = response.strip()

        # Try direct match first
        if response in admissible_actions:
            return response

        # Try to find action in response
        for action in admissible_actions:
            if action.lower() in response.lower():
                return action

        # If no match, log warning and return first action
        logger.warning(f"Could not parse action from response: '{response}'")
        logger.warning(f"Available actions: {admissible_actions}")
        logger.warning("Falling back to first available action")

        return admissible_actions[0] if admissible_actions else "look around"

    def reset(self):
        """Reset conversation history for new episode"""
        self.conversation_history = []
        logger.debug("Reset agent conversation history")
