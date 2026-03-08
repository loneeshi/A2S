"""
Tier 2: Worker Logger - Record worker manager behavior decisions

Records high-level worker actions for quick analysis and debugging.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .context import get_logging_context

logger = logging.getLogger(__name__)


class WorkerLogger:
    """
    Records worker manager behavior at an abstract level
    """

    def __init__(self, run_id: str, model: str, output_dir: Path):
        """
        Initialize worker logger

        Args:
            run_id: Unique run identifier
            model: Model name being used
            output_dir: Directory to save worker_actions.json
        """
        self.run_id = run_id
        self.model = model
        self.output_dir = Path(output_dir)
        self.worker_actions: List[Dict[str, Any]] = []

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"WorkerLogger initialized for run: {run_id}")

    def log_action(
        self,
        task_summary: str,
        action_taken: str,
        decision_rationale: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        duration_ms: Optional[float] = None,
        **kwargs,
    ) -> None:
        """
        Log a worker action

        Args:
            task_summary: Brief description of the task
            action_taken: Action that was taken
            decision_rationale: Why this action was chosen
            tools_used: List of tools used
            duration_ms: Execution duration in milliseconds
            **kwargs: Additional metadata
        """
        # Get context information
        ctx = get_logging_context()

        action_record = {
            "timestamp": datetime.now().isoformat(),
            "episode_id": ctx.episode_id if ctx else None,
            "step": ctx.step if ctx else 0,
            "worker_id": ctx.worker_id if ctx else "unknown",
            "task_summary": task_summary,
            "action_taken": action_taken,
            "decision_rationale": decision_rationale,
            "tools_used": tools_used or [],
            "duration_ms": duration_ms,
        }

        # Add any additional metadata
        action_record.update(kwargs)

        self.worker_actions.append(action_record)
        logger.debug(
            f"Logged worker action: {action_record['worker_id']} - {task_summary}"
        )

        # Real-time write: append to file immediately
        self._append_to_file(action_record)

    def _append_to_file(self, action_record: Dict[str, Any]) -> None:
        """Write all actions to JSON file in real-time"""
        output_path = self.output_dir / "tier2_worker_actions.json"
        try:
            output_data = {
                "run_id": self.run_id,
                "model": self.model,
                "worker_actions": self.worker_actions,
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write worker actions: {e}")

    def save(self) -> Path:
        """
        Save worker actions to JSON file

        Returns:
            Path to the saved file
        """
        output_path = self.output_dir / "tier2_worker_actions.json"

        try:
            output_data = {
                "run_id": self.run_id,
                "model": self.model,
                "worker_actions": self.worker_actions,
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info(
                f"✅ Saved {len(self.worker_actions)} worker actions to {output_path}"
            )
            return output_path

        except Exception as e:
            logger.error(f"❌ Failed to save worker actions: {e}")
            raise

    def get_action_count(self) -> int:
        """Get number of logged actions"""
        return len(self.worker_actions)

    def clear(self) -> None:
        """Clear all logged actions"""
        self.worker_actions.clear()
        logger.debug("Cleared all worker actions")
