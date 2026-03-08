"""
Tier 3: API Call Tracer - Record complete API call context windows

Records full request/response data for each LLM API call for debugging
and optimization.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .context import get_logging_context

logger = logging.getLogger(__name__)


class APICallTracer:
    """
    Traces LLM API calls with complete context windows
    """

    def __init__(self, run_id: str, output_dir: Path):
        """
        Initialize API call tracer

        Args:
            run_id: Unique run identifier
            output_dir: Directory to save api_calls.json
        """
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.api_calls: List[Dict[str, Any]] = []
        self.call_counter = 0

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"APICallTracer initialized for run: {run_id}")

    def trace_call(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any],
        usage: Optional[Dict[str, int]] = None,
        cache_info: Optional[Dict[str, int]] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> str:
        """
        Trace an API call

        Args:
            request: Request data (model, messages, temperature, etc.)
            response: Response data (content, tool_calls, finish_reason)
            usage: Token usage information
            cache_info: Cache hit information
            latency_ms: API call latency in milliseconds
            error: Error message if call failed

        Returns:
            Call ID for this trace
        """
        # Get context information
        ctx = get_logging_context()

        self.call_counter += 1
        call_id = f"call-{self.call_counter:04d}"

        call_record = {
            "call_id": call_id,
            "timestamp": datetime.now().isoformat(),
            "episode_id": ctx.episode_id if ctx else None,
            "step": ctx.step if ctx else 0,
            "worker_id": ctx.worker_id if ctx else "unknown",
            "request": request,
            "response": response,
            "usage": usage or {},
            "cache_info": cache_info or {},
            "latency_ms": latency_ms,
            "error": error,
        }

        self.api_calls.append(call_record)
        logger.debug(f"Traced API call: {call_id} - {request.get('model', 'unknown')}")

        # Real-time write: append to file immediately
        self._append_to_file(call_record)

        return call_id

    def _append_to_file(self, call_record: Dict[str, Any]) -> None:
        """Write all API calls to JSON file in real-time"""
        output_path = self.output_dir / "tier3_api_calls.json"
        try:
            output_data = {"run_id": self.run_id, "api_calls": self.api_calls}
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write API calls: {e}")

    def save(self) -> Path:
        """
        Save API calls to JSON file

        Returns:
            Path to the saved file
        """
        output_path = self.output_dir / "tier3_api_calls.json"

        try:
            output_data = {"run_id": self.run_id, "api_calls": self.api_calls}

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Saved {len(self.api_calls)} API calls to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Failed to save API calls: {e}")
            raise

    def get_call_count(self) -> int:
        """Get number of traced calls"""
        return len(self.api_calls)

    def clear(self) -> None:
        """Clear all traced calls"""
        self.api_calls.clear()
        self.call_counter = 0
        logger.debug("Cleared all API calls")
