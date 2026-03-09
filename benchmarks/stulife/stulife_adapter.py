"""
StuLife Adapter for Auto-Expansion Agent Cluster

Thin wrapper that directly uses StuLife source code.
Provides a simple interface compatible with A2S framework.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Add StuLife source to path
stulife_src_path = Path(__file__).parent.parent / "stulife_source" / "Stulife" / "src"
if str(stulife_src_path) not in sys.path:
    sys.path.insert(0, str(stulife_src_path))

# Import StuLife components
try:
    from tasks.instance.campus_life_bench.task import CampusTask, CampusDatasetItem
    from tasks.instance.campus_life_bench.environment import CampusEnvironment
    from typings import TaskName, Session, SampleStatus, Role
    from factories.chat_history_item import ChatHistoryItemFactory
except ImportError as e:
    raise ImportError(f"Failed to import StuLife components: {e}")

logger = logging.getLogger(__name__)


class StuLifeAdapter:
    """
    Thin adapter for StuLife benchmark

    Provides simple reset/step interface while using full StuLife functionality.
    """

    def __init__(self, data_dir: Optional[str] = None, max_round: int = 10):
        """
        Initialize StuLife adapter

        Args:
            data_dir: Path to StuLife data directory (optional)
            max_round: Maximum interaction rounds per task
        """
        # Set data directory - use task_data with full dataset
        if data_dir is None:
            # Use task_data directory (has tasks.json + background/ with courses.json)
            data_dir = stulife_src_path.parent.parent / "task_data"
            logger.info(f"✅ Using StuLife data directory: {data_dir}")
        self.data_dir = Path(data_dir)

        # Create chat history factory
        chat_history_path = stulife_src_path.parent / "chat_history_items" / "standard" / "campus_life_bench.json"
        self.chat_factory = ChatHistoryItemFactory(
            chat_history_item_dict_path=str(chat_history_path)
        )

        # Create CampusTask instance
        task_name = TaskName(value="campus_life_bench")
        self.campus_task = CampusTask(
            task_name=task_name,
            chat_history_item_factory=self.chat_factory,
            max_round=max_round,
            data_dir=self.data_dir
        )

        # Internal state
        self.current_session: Optional[Session] = None
        self.current_task_id: Optional[str] = None
        self.available_tasks: List[str] = []

        # Load available tasks
        self._load_available_tasks()

        logger.info(f"✅ StuLife adapter initialized with {len(self.available_tasks)} tasks")

    def _load_available_tasks(self):
        """Load list of available task IDs"""
        self.available_tasks = self.campus_task.get_sample_index_list()

    def get_available_tasks(self) -> List[str]:
        """Get list of available task IDs"""
        return self.available_tasks

    def reset(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Reset environment for a new task

        Args:
            task_id: Specific task ID to load (optional, uses first task if None)

        Returns:
            Dictionary with task description and initial state
        """
        # Release previous task if exists
        if self.current_session is not None:
            try:
                self.campus_task.release()
            except Exception as e:
                logger.warning(f"Release failed: {e}, forcing cleanup")
            # Force cleanup of internal state (access private attributes)
            self.campus_task.current_sample_index = None
            self.campus_task._Task__current_dataset_item = None
            self.campus_task.current_round = 0

        # Select task
        if task_id is None:
            if not self.available_tasks:
                raise ValueError("No tasks available")
            task_id = self.available_tasks[0]

        if task_id not in self.available_tasks:
            raise ValueError(f"Task {task_id} not found. Available: {self.available_tasks}")

        self.current_task_id = task_id

        # Create new session
        self.current_session = Session(
            task_name=self.campus_task.task_name,
            sample_index=task_id,
            output_dir="./outputs/adapter_test"
        )

        # Reset task
        self.campus_task.reset(self.current_session)

        # Get initial observation from chat history
        initial_obs = self._get_latest_observation()

        return {
            "task_id": task_id,
            "observation": initial_obs,
            "done": False,
            "info": {
                "round": 0,
                "max_round": self.campus_task.max_round
            }
        }

    def step(self, action: str) -> Dict[str, Any]:
        """
        Execute an action in the environment

        Args:
            action: Action string from agent

        Returns:
            Dictionary with observation, done, success, and info
        """
        if self.current_session is None:
            raise RuntimeError("Must call reset() before step()")

        # Add agent response to session (only if last message is not AGENT)
        from typings import ChatHistoryItem
        chat_history = self.current_session.chat_history
        length = chat_history.get_value_length()

        # Check if we need to inject AGENT message
        should_inject = True
        if length > 0:
            last_msg = chat_history.get_item_deep_copy(length - 1)
            if last_msg.role == Role.AGENT:
                # Last message is already AGENT, don't inject
                should_inject = False
                logger.debug(f"Skipping AGENT inject - last message is already AGENT")

        if should_inject:
            self.current_session.chat_history.inject(
                ChatHistoryItem(role=Role.AGENT, content=action)
            )

        # Let task interact (execute action and get response)
        self.campus_task.interact(self.current_session)

        # Get observation
        observation = self._get_latest_observation()

        # Check if done
        done = self.current_session.sample_status != SampleStatus.RUNNING

        # Get success status
        success = False
        if done:
            from typings import SessionEvaluationOutcome
            success = (self.current_session.evaluation_record.outcome ==
                      SessionEvaluationOutcome.CORRECT)

        return {
            "observation": observation,
            "done": done,
            "success": success,
            "info": {
                "round": self.campus_task.current_round,
                "max_round": self.campus_task.max_round,
                "status": str(self.current_session.sample_status),
                "evaluation": str(self.current_session.evaluation_record.outcome) if done else None
            }
        }

    def _get_latest_observation(self) -> str:
        """Extract latest observation from chat history"""
        if not self.current_session:
            return "No observation available"

        chat_history = self.current_session.chat_history
        length = chat_history.get_value_length()

        if length == 0:
            return "No observation available"

        # Get last message from environment/user (iterate backwards)
        for i in range(length - 1, -1, -1):
            msg = chat_history.get_item_deep_copy(i)
            if msg.role == Role.USER:
                return msg.content

        return "No observation available"

    def get_task_info(self, task_id: str) -> Dict[str, Any]:
        """
        Get information about a specific task

        Args:
            task_id: Task ID

        Returns:
            Dictionary with task metadata
        """
        # Access internal dataset
        dataset_item = self.campus_task._Task__dataset.get(task_id)
        if dataset_item is None:
            return {"error": f"Task {task_id} not found"}

        return {
            "task_id": dataset_item.task_id,
            "task_type": dataset_item.task_type,
            "instruction": dataset_item.instruction,
            "is_trigger": dataset_item.is_trigger,
            "difficulty": dataset_item.get_difficulty_level(),
            "skills": dataset_item.get_skill_list()
        }

    def get_current_session(self) -> Optional[Any]:
        """
        Get the current Session object

        Returns:
            Current Session object or None if no session is active
        """
        if self.current_session is None:
            logger.warning("get_current_session() called but current_session is None")
        else:
            logger.info(f"get_current_session() returning session for task: {self.current_session.sample_index}")
        return self.current_session

    def close(self):
        """Clean up resources"""
        if self.campus_task:
            self.campus_task.release()
        logger.info("StuLife adapter closed")

