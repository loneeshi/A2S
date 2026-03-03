"""
Results Recorder for Auto-Expansion Agent Cluster

This module handles recording and managing test results from different benchmarks.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import csv


logger = logging.getLogger(__name__)


@dataclass
class EpisodeResult:
    """Result of a single episode"""
    episode_id: int
    task_type: str
    agent_used: str
    status: str  # "success" | "failure"
    steps: int
    reward: float
    duration: float
    error_message: Optional[str] = None


@dataclass
class BenchmarkResults:
    """Complete results from a benchmark run"""
    benchmark_name: str
    timestamp: str
    config: Dict[str, Any]
    tree_config: Dict[str, Any]
    episodes: List[EpisodeResult]
    summary: Dict[str, Any]


class ResultsRecorder:
    """
    Record and manage test results

    Usage:
        recorder = ResultsRecorder()

        # Initialize a new test run
        run_id = recorder.initialize_run("alfworld", {...})

        # Record episode results
        recorder.record_episode(run_id, {...})

        # Finalize and save results
        recorder.finalize_run(run_id)
    """

    def __init__(self, results_dir: Optional[str] = None):
        """Initialize results recorder"""
        if results_dir is None:
            current_file = Path(__file__)
            project_root = current_file.parent.parent
            results_dir = project_root / "results"

        self.results_dir = Path(results_dir)
        self.current_runs: Dict[str, Dict[str, Any]] = {}

    def initialize_run(
        self,
        benchmark_name: str,
        config: Dict[str, Any],
        tree_config: Dict[str, Any]
    ) -> str:
        """
        Initialize a new test run

        Args:
            benchmark_name: Name of benchmark (e.g., "alfworld", "stulife")
            config: Test configuration
            tree_config: Agent tree configuration

        Returns:
            run_id: Unique identifier for this run
        """
        timestamp = datetime.now().isoformat()
        run_id = f"{benchmark_name}_{timestamp.replace(':', '-').replace('.', '-')}"

        run_info = {
            "run_id": run_id,
            "benchmark_name": benchmark_name,
            "timestamp": timestamp,
            "config": config,
            "tree_config": tree_config,
            "episodes": [],
            "start_time": datetime.now().isoformat(),
        }

        self.current_runs[run_id] = run_info

        logger.info(f"Initialized run: {run_id}")
        return run_id

    def record_episode(
        self,
        run_id: str,
        episode_id: int,
        task_type: str,
        agent_used: str,
        status: str,
        steps: int,
        reward: float,
        duration: float,
        error_message: Optional[str] = None
    ) -> None:
        """Record a single episode result"""
        if run_id not in self.current_runs:
            logger.error(f"Unknown run_id: {run_id}")
            return

        episode_result = EpisodeResult(
            episode_id=episode_id,
            task_type=task_type,
            agent_used=agent_used,
            status=status,
            steps=steps,
            reward=reward,
            duration=duration,
            error_message=error_message
        )

        self.current_runs[run_id]["episodes"].append(asdict(episode_result))
        logger.debug(f"Recorded episode {episode_id}: {status}")

    def finalize_run(self, run_id: str) -> BenchmarkResults:
        """
        Finalize a run and save results

        Args:
            run_id: Run identifier

        Returns:
            BenchmarkResults object
        """
        if run_id not in self.current_runs:
            logger.error(f"Unknown run_id: {run_id}")
            return None

        run_info = self.current_runs[run_id]
        run_info["end_time"] = datetime.now().isoformat()

        # Calculate summary
        episodes = run_info["episodes"]
        total_episodes = len(episodes)
        successful_episodes = sum(1 for e in episodes if e["status"] == "success")
        failed_episodes = total_episodes - successful_episodes
        success_rate = successful_episodes / total_episodes if total_episodes > 0 else 0.0

        # Per-agent stats
        agent_stats = {}
        for episode in episodes:
            agent = episode["agent_used"]
            if agent not in agent_stats:
                agent_stats[agent] = {"total": 0, "success": 0, "failed": 0}
            agent_stats[agent]["total"] += 1
            if episode["status"] == "success":
                agent_stats[agent]["success"] += 1
            else:
                agent_stats[agent]["failed"] += 1

        # Calculate success rates per agent
        for agent in agent_stats:
            stats = agent_stats[agent]
            agent_stats[agent]["success_rate"] = stats["success"] / stats["total"]

        # Per-task-type stats
        task_type_stats = {}
        for episode in episodes:
            task_type = episode["task_type"]
            if task_type not in task_type_stats:
                task_type_stats[task_type] = {"total": 0, "success": 0}
            task_type_stats[task_type]["total"] += 1
            if episode["status"] == "success":
                task_type_stats[task_type]["success"] += 1

        for task_type in task_type_stats:
            stats = task_type_stats[task_type]
            task_type_stats[task_type]["success_rate"] = stats["success"] / stats["total"]

        summary = {
            "total_episodes": total_episodes,
            "successful_episodes": successful_episodes,
            "failed_episodes": failed_episodes,
            "success_rate": success_rate,
            "agent_stats": agent_stats,
            "task_type_stats": task_type_stats,
        }

        run_info["summary"] = summary

        # Save results
        benchmark_dir = self.results_dir / run_info["benchmark_name"]
        benchmark_dir.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        json_path = benchmark_dir / f"{run_id}.json"
        with open(json_path, 'w') as f:
            json.dump(run_info, f, indent=2)

        # Save as CSV (episodes only)
        csv_path = benchmark_dir / f"{run_id}.csv"
        with open(csv_path, 'w', newline='') as f:
            if episodes:
                writer = csv.DictWriter(f, fieldnames=episodes[0].keys())
                writer.writeheader()
                writer.writerows(episodes)

        # Save summary as text
        summary_path = benchmark_dir / f"{run_id}_summary.txt"
        with open(summary_path, 'w') as f:
            f.write(f"Benchmark: {run_info['benchmark_name']}\n")
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Timestamp: {run_info['timestamp']}\n")
            f.write(f"\n=== Summary ===\n\n")
            f.write(f"Total Episodes: {total_episodes}\n")
            f.write(f"Successful: {successful_episodes}\n")
            f.write(f"Failed: {failed_episodes}\n")
            f.write(f"Success Rate: {success_rate:.2%}\n")
            f.write(f"\n=== Agent Performance ===\n\n")
            for agent, stats in agent_stats.items():
                f.write(f"{agent}:\n")
                f.write(f"  Total: {stats['total']}\n")
                f.write(f"  Success: {stats['success']}\n")
                f.write(f"  Failed: {stats['failed']}\n")
                f.write(f"  Success Rate: {stats['success_rate']:.2%}\n")
            f.write(f"\n=== Task Type Performance ===\n\n")
            for task_type, stats in task_type_stats.items():
                f.write(f"{task_type}:\n")
                f.write(f"  Total: {stats['total']}\n")
                f.write(f"  Success: {stats['success']}\n")
                f.write(f"  Success Rate: {stats['success_rate']:.2%}\n")

        logger.info(f"Results saved:")
        logger.info(f"  JSON: {json_path}")
        logger.info(f"  CSV: {csv_path}")
        logger.info(f"  Summary: {summary_path}")

        # Remove from current runs
        del self.current_runs[run_id]

        return BenchmarkResults(
            benchmark_name=run_info["benchmark_name"],
            timestamp=run_info["timestamp"],
            config=run_info["config"],
            tree_config=run_info["tree_config"],
            episodes=episodes,
            summary=summary
        )

    def list_runs(self, benchmark_name: Optional[str] = None) -> List[str]:
        """List all saved runs for a benchmark"""
        if benchmark_name:
            benchmark_dir = self.results_dir / benchmark_name
        else:
            benchmark_dir = self.results_dir

        if not benchmark_dir.exists():
            return []

        json_files = list(benchmark_dir.glob("*.json"))
        return sorted([f.stem for f in json_files])

    def load_results(self, benchmark_name: str, run_id: str) -> Dict[str, Any]:
        """Load results from a previous run"""
        json_path = self.results_dir / benchmark_name / f"{run_id}.json"
        if not json_path.exists():
            logger.error(f"Results not found: {json_path}")
            return None

        with open(json_path, 'r') as f:
            return json.load(f)

    def get_latest_run_id(self, benchmark_name: str) -> Optional[str]:
        """Get the most recent run ID for a benchmark"""
        run_ids = self.list_runs(benchmark_name)
        if run_ids:
            return run_ids[-1]  # Last one is most recent
        return None
