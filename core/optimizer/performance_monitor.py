"""
Performance Monitor for Auto-Expansion Agent Cluster

This module monitors agent performance during testing and tracks
metrics that inform dynamic extension decisions.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

from ..generator.tree_builder import AgentTree
from core.reflection import get_reflection_agent


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a task execution"""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    """Result of a single task execution"""

    task_id: str
    task_type: str
    status: TaskStatus
    agent_used: str
    duration: float  # seconds
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "agent_used": self.agent_used,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class AgentMetrics:
    """Metrics for a single agent"""

    agent_name: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_duration: float = 0.0
    average_duration: float = 0.0
    success_rate: float = 0.0
    task_types: Dict[str, int] = field(default_factory=dict)

    def update(self, result: TaskResult):
        """Update metrics with a new task result"""
        self.total_tasks += 1
        self.total_duration += result.duration

        if result.status == TaskStatus.SUCCESS:
            self.successful_tasks += 1
        else:
            self.failed_tasks += 1

        # Track task types
        if result.task_type not in self.task_types:
            self.task_types[result.task_type] = 0
        self.task_types[result.task_type] += 1

        # Recompute averages
        self.average_duration = self.total_duration / self.total_tasks
        self.success_rate = self.successful_tasks / self.total_tasks


class PerformanceMonitor:
    """
    Monitor agent performance during testing

    Tracks:
    - Task success/failure rates
    - Agent-specific performance
    - Task type difficulties
    - Overall system performance

    This data informs the dynamic extension engine.
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize performance monitor

        Args:
            window_size: Number of recent tasks to keep in rolling window
        """
        self.window_size = window_size
        self.task_history: List[TaskResult] = []
        self.agent_metrics: Dict[str, AgentMetrics] = {}
        self.task_type_metrics: Dict[str, Dict[str, Any]] = {}

    def record_task_result(self, result: TaskResult) -> None:
        """
        Record a task result

        Args:
            result: TaskResult to record
        """
        # Add to history (maintain window size)
        self.task_history.append(result)
        if len(self.task_history) > self.window_size:
            self.task_history.pop(0)

        # Update agent metrics
        if result.agent_used not in self.agent_metrics:
            self.agent_metrics[result.agent_used] = AgentMetrics(
                agent_name=result.agent_used
            )
        self.agent_metrics[result.agent_used].update(result)

        # Update task type metrics
        if result.task_type not in self.task_type_metrics:
            self.task_type_metrics[result.task_type] = {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
            }

        self.task_type_metrics[result.task_type]["total"] += 1
        if result.status == TaskStatus.SUCCESS:
            self.task_type_metrics[result.task_type]["successful"] += 1
        else:
            self.task_type_metrics[result.task_type]["failed"] += 1

        # Recompute success rate
        metrics = self.task_type_metrics[result.task_type]
        metrics["success_rate"] = metrics["successful"] / metrics["total"]

        logger.debug(
            f"Recorded task {result.task_id}: "
            f"{result.status.value} by {result.agent_used}"
        )

        # Check if inline reflection should be triggered
        if result.status != TaskStatus.SUCCESS:
            try:
                recent_failures = [
                    t for t in self.task_history[-10:] if t.status != TaskStatus.SUCCESS
                ]
                recent_rate = self.get_recent_performance(n=5).get("success_rate", 1.0)

                if len(recent_failures) >= 3 or recent_rate < 0.3:
                    reflection_agent = get_reflection_agent()
                    failure_info = {
                        "domain": result.task_type,
                        "task_type": result.task_type,
                        "agent_name": result.agent_used,
                        "episode_id": result.task_id,
                        "error_message": result.error_message or "Task failed",
                        "action_history": result.metadata.get("action_history", []),
                        "observation": result.metadata.get("observation", ""),
                        "tools_used": result.metadata.get("tools_used", []),
                        "success_rate": self.get_overall_success_rate(),
                    }
                    reflection = reflection_agent.analyze_failure(failure_info)
                    logger.info(
                        f"Inline reflection: {reflection.failure_type} "
                        f"(confidence={reflection.confidence:.2f}, "
                        f"action={reflection.prompt_update_action.value})"
                    )
            except Exception as e:
                logger.debug(f"Inline reflection skipped: {e}")

    def get_overall_success_rate(self) -> float:
        """Get overall success rate across all tasks"""
        if not self.task_history:
            return 0.0

        successful = sum(1 for t in self.task_history if t.status == TaskStatus.SUCCESS)
        return successful / len(self.task_history)

    def get_agent_performance(self, agent_name: str) -> Optional[AgentMetrics]:
        """Get metrics for a specific agent"""
        return self.agent_metrics.get(agent_name)

    def get_underperforming_agents(self, threshold: float = 0.7) -> List[str]:
        """
        Get list of underperforming agents

        Args:
            threshold: Success rate threshold (default 0.7 = 70%)

        Returns:
            List of agent names with success rate below threshold
        """
        return [
            name
            for name, metrics in self.agent_metrics.items()
            if metrics.success_rate < threshold
        ]

    def get_difficult_task_types(self, threshold: float = 0.5) -> List[str]:
        """
        Get list of difficult task types

        Args:
            threshold: Success rate threshold (default 0.5 = 50%)

        Returns:
            List of task types with success rate below threshold
        """
        return [
            task_type
            for task_type, metrics in self.task_type_metrics.items()
            if metrics["success_rate"] < threshold
        ]

    def get_recent_performance(self, n: int = 10) -> Dict[str, Any]:
        """
        Get performance metrics for recent N tasks

        Args:
            n: Number of recent tasks to analyze

        Returns:
            Dict with performance metrics
        """
        recent = (
            self.task_history[-n:] if len(self.task_history) >= n else self.task_history
        )

        if not recent:
            return {"count": 0, "success_rate": 0.0}

        successful = sum(1 for t in recent if t.status == TaskStatus.SUCCESS)
        return {
            "count": len(recent),
            "successful": successful,
            "failed": len(recent) - successful,
            "success_rate": successful / len(recent),
            "average_duration": sum(t.duration for t in recent) / len(recent),
        }

    def should_trigger_extension(self, threshold: float = 0.7) -> bool:
        """
        Determine if performance is low enough to trigger extension

        Args:
            threshold: Success rate threshold (default 0.7)

        Returns:
            True if extension should be triggered
        """
        # Check overall success rate
        overall_rate = self.get_overall_success_rate()
        if overall_rate < threshold:
            logger.info(
                f"Extension trigger: overall success rate {overall_rate:.2f} < {threshold}"
            )
            return True

        # Check for difficult task types
        difficult = self.get_difficult_task_types(threshold=0.5)
        if difficult:
            logger.info(f"Extension trigger: difficult task types: {difficult}")
            return True

        # Check for underperforming agents
        underperforming = self.get_underperforming_agents(threshold)
        if underperforming:
            logger.info(f"Extension trigger: underperforming agents: {underperforming}")
            return True

        return False

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        return {
            "total_tasks": len(self.task_history),
            "overall_success_rate": self.get_overall_success_rate(),
            "agent_count": len(self.agent_metrics),
            "task_type_count": len(self.task_type_metrics),
            "agent_metrics": {
                name: {
                    "success_rate": metrics.success_rate,
                    "total_tasks": metrics.total_tasks,
                    "average_duration": metrics.average_duration,
                }
                for name, metrics in self.agent_metrics.items()
            },
            "task_type_metrics": self.task_type_metrics,
            "recent_performance": self.get_recent_performance(n=10),
        }

    def reset(self) -> None:
        """Reset all metrics"""
        self.task_history.clear()
        self.agent_metrics.clear()
        self.task_type_metrics.clear()
        logger.info("Performance monitor reset")
