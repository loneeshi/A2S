"""
Tier 1: Session Collector - Generate StuLife native runs.json format

Collects Session objects from StuLife adapter and generates runs.json
compatible with calculate_stulife_metrics.py
"""

import json
import logging
from pathlib import Path
from typing import List, Optional, Any, Dict

logger = logging.getLogger(__name__)


class SessionCollector:
    """
    Collects Session objects and generates runs.json in StuLife native format
    """

    def __init__(self, model_name: str, output_dir: Path):
        """
        Initialize session collector

        Args:
            model_name: Name of the model being evaluated
            output_dir: Output directory (run-specific directory)
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.sessions: List[Any] = []

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"SessionCollector initialized for model: {model_name}")
        logger.info(f"Output directory: {self.output_dir}")

    def add_session(self, session: Any) -> None:
        """
        Add a Session object to the collection

        Args:
            session: StuLife Session object
        """
        if session is None:
            logger.warning("Attempted to add None session, skipping")
            return

        self.sessions.append(session)
        logger.debug(f"Added session for task: {session.sample_index}")

        # Real-time write: append to file immediately
        self._append_to_file(session)

    def _append_to_file(self, session: Any) -> None:
        """Write all sessions to JSON file in real-time"""
        output_path = self.output_dir / "tier1_runs.json"
        try:
            runs_data = []
            for s in self.sessions:
                session_dict = s.model_dump()
                runs_data.append(session_dict)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(runs_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write sessions: {e}")

    def save_runs_json(self) -> Path:
        """
        Save all collected sessions to runs.json

        Returns:
            Path to the saved runs.json file
        """
        output_path = self.output_dir / "tier1_runs.json"

        try:
            # Convert sessions to dictionaries
            runs_data = []
            for session in self.sessions:
                # Use model_dump() to serialize Session object
                session_dict = session.model_dump()
                runs_data.append(session_dict)

            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(runs_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Saved {len(runs_data)} sessions to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"❌ Failed to save runs.json: {e}")
            raise

    def get_session_count(self) -> int:
        """Get number of collected sessions"""
        return len(self.sessions)

    def clear(self) -> None:
        """Clear all collected sessions"""
        self.sessions.clear()
        logger.debug("Cleared all sessions")
