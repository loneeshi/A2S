"""
StuLife-specific detailed logger for tracking execution details.
Preserves the detailed logging format from StuLife's native test runner.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum


class StuLifeLogger:
    """Detailed logger for StuLife benchmark execution."""

    def __init__(self, run_id: str, output_dir: str = "results/stulife"):
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create detailed log file
        self.log_file = self.output_dir / f"{run_id}_detailed.log"
        self.json_file = self.output_dir / f"{run_id}_detailed.json"

        # Initialize data structures
        self.episodes_data: List[Dict[str, Any]] = []
        self.current_episode: Optional[Dict[str, Any]] = None

        # Setup file logger
        self.logger = logging.getLogger(f"stulife_{run_id}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        fh = logging.FileHandler(self.log_file, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Also log to console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def start_episode(self, episode_id: int, task_id: str, task_description: str, max_rounds: int):
        """Start logging a new episode."""
        self.current_episode = {
            "episode_id": episode_id,
            "task_id": task_id,
            "task_description": task_description,
            "max_rounds": max_rounds,
            "start_time": datetime.now().isoformat(),
            "rounds": [],
            "success": False,
            "finish_reason": None,
            "evaluation_outcome": None,
            "total_rounds_used": 0,
        }

        self.logger.info("=" * 80)
        self.logger.info(f"🎯 Episode {episode_id} Started")
        self.logger.info(f"📋 Task ID: {task_id}")
        self.logger.info(f"📝 Task Description: {task_description}")
        self.logger.info(f"🔄 Max Rounds: {max_rounds}")
        self.logger.info("=" * 80)

    def log_round_start(self, round_num: int, max_rounds: int):
        """Log the start of a round."""
        self.logger.info(f"\n🔄 Round {round_num}/{max_rounds}")

    def log_agent_response(self, response: str):
        """Log the agent's response."""
        self.logger.info(f"📝 Agent response: {repr(response)}")

    def log_parsed_action(self, action_type: str, content: str):
        """Log the parsed action from agent response."""
        self.logger.info(f"🔍 Parsed action: {action_type}")
        self.logger.info(f"🔍 Parsed content: {content}")

    def log_action_execution(self, action_type: str):
        """Log action execution."""
        if action_type == "execute":
            self.logger.info("⚙️  Action executed via _interact method")
        elif action_type == "finish":
            self.logger.info("✅ Task finished")
        elif action_type == "invalid":
            self.logger.warning("⚠️  Invalid action format")

    def log_observation(self, observation: str):
        """Log the observation received."""
        self.logger.info(f"👁️  Observation: {observation[:200]}..." if len(observation) > 200 else f"👁️  Observation: {observation}")

    def record_round(self, round_num: int, agent_response: str, parsed_action: Dict[str, Any],
                     observation: str, round_duration: float):
        """Record complete round data."""
        if self.current_episode is None:
            return

        round_data = {
            "round_num": round_num,
            "agent_response": agent_response,
            "parsed_action": parsed_action,
            "observation": observation,
            "duration": round_duration,
            "timestamp": datetime.now().isoformat()
        }

        self.current_episode["rounds"].append(round_data)
        self.logger.info(f"⏱️  Round duration: {round_duration:.2f}s")

    def end_episode(self, success: bool, finish_reason: str, evaluation_outcome: str,
                    rounds_used: int, episode_duration: float, chat_history: Optional[List] = None):
        """End the current episode and save data."""
        if self.current_episode is None:
            return

        self.current_episode.update({
            "success": success,
            "finish_reason": finish_reason,
            "evaluation_outcome": evaluation_outcome,
            "total_rounds_used": rounds_used,
            "end_time": datetime.now().isoformat(),
            "total_duration": episode_duration,
            "chat_history": chat_history or []
        })

        self.logger.info("\n" + "=" * 80)
        self.logger.info(f"🏁 Episode {self.current_episode['episode_id']} Completed")
        self.logger.info(f"✅ Success: {success}")
        self.logger.info(f"📊 Evaluation Outcome: {evaluation_outcome}")
        self.logger.info(f"🔄 Rounds Used: {rounds_used}/{self.current_episode['max_rounds']}")
        self.logger.info(f"⏱️  Total Duration: {episode_duration:.2f}s")
        self.logger.info(f"🏁 Finish Reason: {finish_reason}")
        self.logger.info("=" * 80 + "\n")

        self.episodes_data.append(self.current_episode)
        self.current_episode = None

    def save_detailed_results(self):
        """Save all detailed results to JSON file."""
        output_data = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "total_episodes": len(self.episodes_data),
            "episodes": self.episodes_data
        }

        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"💾 Detailed results saved to: {self.json_file}")

    def log_error(self, error_msg: str, exception: Optional[Exception] = None):
        """Log an error."""
        self.logger.error(f"🚨 Error: {error_msg}")
        if exception:
            self.logger.error(f"🚨 Exception: {str(exception)}")

    def log_warning(self, warning_msg: str):
        """Log a warning."""
        self.logger.warning(f"🚧 Warning: {warning_msg}")
