"""
Environment Explorer for Auto-Expansion Agent Cluster

This module implements Phase 2 of hybrid initialization:
Environment exploration to refine the initial agent tree.

The explorer runs episodes, analyzes performance gaps, and generates
refinements to improve the agent tree.
"""

from typing import Dict, List, Any, Optional
import logging
from dataclasses import dataclass
from enum import Enum

from .tree_builder import AgentTree, AgentDefinition
from .description_reader import BenchmarkDescriptionReader


logger = logging.getLogger(__name__)


class ExplorationResult(Enum):
    """Possible results from exploration episode"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class EpisodeResult:
    """Result of a single exploration episode"""
    episode_id: int
    task_type: str
    result: ExplorationResult
    agent_used: str
    error_message: Optional[str] = None
    performance_metrics: Dict[str, Any] = None

    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {}


@dataclass
class GapAnalysis:
    """Analysis of performance gaps"""
    missing_tools: List[str]  # Tools that are needed but not available
    weak_agents: List[str]  # Agent names that underperform
    uncovered_tasks: List[str]  # Task types not covered well
    suggested_additions: List[Dict[str, Any]]  # Suggested new agents/tools
    performance_score: float  # Overall performance (0-1)


class EnvironmentExplorer:
    """
    Explore environment and refine agent tree

    Process:
    1. Run exploration episodes with initial tree
    2. Analyze performance gaps
    3. Generate refinement suggestions
    4. Apply refinements to tree
    """

    def __init__(
        self,
        description_reader: Optional[BenchmarkDescriptionReader] = None,
        num_episodes: int = 10
    ):
        """
        Initialize the environment explorer

        Args:
            description_reader: Reader for benchmark intros
            num_episodes: Number of exploration episodes to run
        """
        self.description_reader = description_reader or BenchmarkDescriptionReader()
        self.num_episodes = num_episodes

    def explore_and_refine(
        self,
        initial_tree: AgentTree,
        benchmark_name: str
    ) -> AgentTree:
        """
        Explore environment and refine agent tree

        Args:
            initial_tree: Initial agent tree from description-based generation
            benchmark_name: Name of the benchmark

        Returns:
            Refined agent tree
        """
        logger.info(f"Starting environment exploration for {benchmark_name}")

        # Step 1: Run exploration episodes
        episode_results = self._run_exploration_episodes(
            initial_tree,
            benchmark_name
        )

        # Step 2: Analyze gaps
        gap_analysis = self._analyze_gaps(
            initial_tree,
            episode_results,
            benchmark_name
        )

        # Step 3: Generate refinements
        refined_tree = self._apply_refinements(
            initial_tree,
            gap_analysis
        )

        # Update metadata
        refined_tree.metadata["exploration_results"] = {
            "num_episodes": len(episode_results),
            "gap_analysis": gap_analysis.__dict__,
            "performance_score": gap_analysis.performance_score,
        }

        logger.info(
            f"Exploration complete. Performance score: {gap_analysis.performance_score:.2f}"
        )

        return refined_tree

    def _run_exploration_episodes(
        self,
        tree: AgentTree,
        benchmark_name: str
    ) -> List[EpisodeResult]:
        """
        Run exploration episodes

        Args:
            tree: Agent tree to test
            benchmark_name: Benchmark name

        Returns:
            List of episode results
        """
        results = []

        # Get task types from benchmark
        intro = self.description_reader.read_benchmark_intro(benchmark_name)
        task_types = [task.name for task in intro.task_types]

        logger.info(f"Running {self.num_episodes} episodes across {len(task_types)} task types")

        for i in range(self.num_episodes):
            # Select a task type (round-robin for now)
            task_type = task_types[i % len(task_types)]

            # Simulate running an episode
            # In real implementation, this would actually execute in the environment
            result = self._simulate_episode(tree, task_type, i)
            results.append(result)

        return results

    def _simulate_episode(
        self,
        tree: AgentTree,
        task_type: str,
        episode_id: int
    ) -> EpisodeResult:
        """
        Simulate running an exploration episode

        In real implementation, this would:
        1. Load environment
        2. Select appropriate agent
        3. Execute task
        4. Record result

        For now, returns simulated results
        """
        # Find appropriate worker for task type
        agent = self._select_agent_for_task(tree, task_type)

        # Simulate result (90% success for now)
        import random
        success = random.random() < 0.9

        if success:
            result = ExplorationResult.SUCCESS
            error = None
        else:
            result = ExplorationResult.FAILURE
            error = "Simulated failure for testing"

        return EpisodeResult(
            episode_id=episode_id,
            task_type=task_type,
            result=result,
            agent_used=agent.name if agent else "Unknown",
            error_message=error,
            performance_metrics={"simulated": True}
        )

    def _select_agent_for_task(
        self,
        tree: AgentTree,
        task_type: str
    ) -> Optional[AgentDefinition]:
        """Select appropriate agent for a task type"""
        # Simple heuristic: match task type to worker domain
        for worker in tree.workers:
            if worker.domain and worker.domain in task_type.lower():
                return worker
            if worker.metadata.get("category") in task_type.lower():
                return worker
        # Return first worker as fallback
        return tree.workers[0] if tree.workers else None

    def _analyze_gaps(
        self,
        tree: AgentTree,
        episode_results: List[EpisodeResult],
        benchmark_name: str
    ) -> GapAnalysis:
        """
        Analyze performance gaps from episode results

        Args:
            tree: Agent tree that was tested
            episode_results: Results from exploration episodes
            benchmark_name: Benchmark name

        Returns:
            GapAnalysis with identified issues
        """
        # Calculate success rate
        success_count = sum(
            1 for r in episode_results
            if r.result == ExplorationResult.SUCCESS
        )
        success_rate = success_count / len(episode_results) if episode_results else 0

        # Identify weak agents (those with failures)
        agent_failures = {}
        for result in episode_results:
            if result.result != ExplorationResult.SUCCESS:
                agent_failures[result.agent_used] = \
                    agent_failures.get(result.agent_used, 0) + 1

        weak_agents = [
            agent for agent, count in agent_failures.items()
            if count > 1  # More than 1 failure
        ]

        # Get all required tools from benchmark
        intro = self.description_reader.read_benchmark_intro(benchmark_name)
        all_required_tools = set()
        for task in intro.task_types:
            all_required_tools.update(task.tools)

        # Find tools we have
        available_tools = set()
        for worker in tree.workers:
            available_tools.update(worker.tools)

        # Find missing tools
        missing_tools = list(all_required_tools - available_tools)

        # Identify uncovered tasks (those with low success rate)
        task_success = {}
        for result in episode_results:
            if result.task_type not in task_success:
                task_success[result.task_type] = {"success": 0, "total": 0}
            task_success[result.task_type]["total"] += 1
            if result.result == ExplorationResult.SUCCESS:
                task_success[result.task_type]["success"] += 1

        uncovered_tasks = [
            task for task, stats in task_success.items()
            if stats["success"] / stats["total"] < 0.5  # Less than 50% success
        ]

        # Generate suggestions
        suggested_additions = []
        if missing_tools:
            suggested_additions.append({
                "type": "add_tools",
                "tools": missing_tools,
                "reason": "Required tools not available in current tree"
            })
        if uncovered_tasks:
            suggested_additions.append({
                "type": "add_workers",
                "task_types": uncovered_tasks,
                "reason": "Task types with low success rate"
            })

        return GapAnalysis(
            missing_tools=missing_tools,
            weak_agents=weak_agents,
            uncovered_tasks=uncovered_tasks,
            suggested_additions=suggested_additions,
            performance_score=success_rate
        )

    def _apply_refinements(
        self,
        tree: AgentTree,
        gap_analysis: GapAnalysis
    ) -> AgentTree:
        """
        Apply refinements based on gap analysis

        Args:
            tree: Current agent tree
            gap_analysis: Analysis of gaps

        Returns:
            Refined agent tree
        """
        # Create a copy of the tree
        refined_tree = AgentTree(
            workers=tree.workers.copy(),
            managers=tree.managers.copy(),
            metadata=tree.metadata.copy()
        )

        # Apply suggestions
        for suggestion in gap_analysis.suggested_additions:
            if suggestion["type"] == "add_tools":
                logger.info(f"Adding tools: {suggestion['tools']}")
                # Add tools to appropriate workers
                # (This is a simplified implementation)
                pass
            elif suggestion["type"] == "add_workers":
                logger.info(f"Adding workers for: {suggestion['task_types']}")
                # Create new workers for uncovered tasks
                # (This is a simplified implementation)
                pass

        return refined_tree
