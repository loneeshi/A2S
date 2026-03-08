"""
Central Coordinator for Three-Tier Logging System

Manages the lifecycle of all three logging tiers and ensures consistency.
"""

import logging
from pathlib import Path
from typing import Optional, Any

from .session_collector import SessionCollector
from .worker_logger import WorkerLogger
from .api_tracer import APICallTracer
from .context import LoggingContext, set_logging_context, clear_logging_context

logger = logging.getLogger(__name__)


class LoggingCoordinator:
    """
    Central coordinator for three-tier logging system

    Manages:
    - Tier 1: Session collection for runs.json
    - Tier 2: Worker behavior logging
    - Tier 3: API call tracing
    """

    def __init__(
        self,
        run_id: str,
        benchmark: str,
        model: str,
        output_dir: Path,
        stulife_result_dir: Optional[Path] = None,
    ):
        """
        Initialize logging coordinator

        Args:
            run_id: Unique run identifier
            benchmark: Benchmark name (e.g., "stulife")
            model: Model name being evaluated
            output_dir: Base output directory (will create run_id subdirectory)
            stulife_result_dir: Optional override for Tier 1 output (deprecated)
        """
        self.run_id = run_id
        self.benchmark = benchmark
        self.model = model

        # Create run-specific directory: output_dir/run_id/
        self.run_output_dir = Path(output_dir) / run_id
        self.run_output_dir.mkdir(parents=True, exist_ok=True)

        self.output_dir = self.run_output_dir

        # All three tiers go to the same directory
        # Initialize three logging tiers
        self.session_collector = SessionCollector(
            model_name=model, output_dir=self.run_output_dir
        )

        self.worker_logger = WorkerLogger(
            run_id=run_id, model=model, output_dir=self.run_output_dir
        )

        self.api_tracer = APICallTracer(run_id=run_id, output_dir=self.run_output_dir)

        # Current episode context
        self.current_context: Optional[LoggingContext] = None

        logger.info(f"LoggingCoordinator initialized for run: {run_id}")
        logger.info(f"  Benchmark: {benchmark}")
        logger.info(f"  Model: {model}")
        logger.info(f"  Run output dir: {self.run_output_dir}")

    def start_episode(self, episode_id: str, task_id: str, step: int = 0) -> None:
        """
        Start a new episode

        Args:
            episode_id: Episode identifier (e.g., "ep-000")
            task_id: Task identifier
            step: Initial step number
        """
        # Create and set context
        self.current_context = LoggingContext(
            episode_id=episode_id,
            task_id=task_id,
            step=step,
            worker_id="stulife_worker",
            run_id=self.run_id,
        )
        set_logging_context(self.current_context)

        logger.info(f"Started episode: {episode_id} (task: {task_id})")

    def end_episode(self, episode_id: str, session: Optional[Any] = None) -> None:
        """
        End an episode

        Args:
            episode_id: Episode identifier
            session: StuLife Session object (for Tier 1)
        """
        # Add session to collector if provided
        if session is not None:
            self.session_collector.add_session(session)
            logger.debug(f"Added session for episode: {episode_id}")

        # Clear context
        clear_logging_context()
        self.current_context = None

        logger.info(f"Ended episode: {episode_id}")

    def update_step(self, step: int) -> None:
        """
        Update current step number

        Args:
            step: New step number
        """
        if self.current_context:
            self.current_context.step = step
            set_logging_context(self.current_context)

    def log_worker_action(
        self,
        task_summary: str,
        action_taken: str,
        decision_rationale: Optional[str] = None,
        tools_used: Optional[list] = None,
        duration_ms: Optional[float] = None,
        **kwargs,
    ) -> None:
        """
        Log a worker action (Tier 2)

        Args:
            task_summary: Brief task description
            action_taken: Action that was taken
            decision_rationale: Why this action was chosen
            tools_used: List of tools used
            duration_ms: Execution duration
            **kwargs: Additional metadata
        """
        self.worker_logger.log_action(
            task_summary=task_summary,
            action_taken=action_taken,
            decision_rationale=decision_rationale,
            tools_used=tools_used,
            duration_ms=duration_ms,
            **kwargs,
        )

    def trace_api_call(
        self,
        request: dict,
        response: dict,
        usage: Optional[dict] = None,
        cache_info: Optional[dict] = None,
        latency_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> str:
        """
        Trace an API call (Tier 3)

        Args:
            request: Request data
            response: Response data
            usage: Token usage
            cache_info: Cache information
            latency_ms: Latency in milliseconds
            error: Error message if failed

        Returns:
            Call ID
        """
        return self.api_tracer.trace_call(
            request=request,
            response=response,
            usage=usage,
            cache_info=cache_info,
            latency_ms=latency_ms,
            error=error,
        )

    def finalize(self) -> dict:
        """
        Finalize logging and save all data

        Returns:
            Dictionary with paths to saved files
        """
        logger.info("Finalizing three-tier logging...")

        try:
            # Save Tier 1: runs.json
            runs_json_path = self.session_collector.save_runs_json()

            # Save Tier 2: worker_actions.json
            worker_actions_path = self.worker_logger.save()

            # Save Tier 3: api_calls.json
            api_calls_path = self.api_tracer.save()

            result = {
                "tier1_runs_json": str(runs_json_path),
                "tier2_worker_actions": str(worker_actions_path),
                "tier3_api_calls": str(api_calls_path),
                "session_count": self.session_collector.get_session_count(),
                "worker_action_count": self.worker_logger.get_action_count(),
                "api_call_count": self.api_tracer.get_call_count(),
            }

            logger.info("✅ Three-tier logging finalized successfully")
            logger.info(f"  Sessions: {result['session_count']}")
            logger.info(f"  Worker actions: {result['worker_action_count']}")
            logger.info(f"  API calls: {result['api_call_count']}")

            return result

        except Exception as e:
            logger.error(f"❌ Failed to finalize logging: {e}")
            raise

    def get_stats(self) -> dict:
        """
        Get current logging statistics

        Returns:
            Dictionary with current counts
        """
        return {
            "run_id": self.run_id,
            "sessions": self.session_collector.get_session_count(),
            "worker_actions": self.worker_logger.get_action_count(),
            "api_calls": self.api_tracer.get_call_count(),
        }
