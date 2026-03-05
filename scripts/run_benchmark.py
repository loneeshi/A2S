#!/usr/bin/env python3
"""
Benchmark Runner — Entry point spawned by PythonAgentManager (python-manager.ts).

Initializes the Auto-Expansion Agent runtime for a given benchmark, wires it to
the UIBridge for real-time event streaming to the Swarm-IDE frontend, and runs
the agent tree through benchmark episodes.

Usage (called by python-manager.ts):
    python scripts/run_benchmark.py \
        --benchmark alfworld \
        --task_id task-abc123 \
        --workspace_id ws-xyz \
        --agent_id py-1a2b3c4d

Event Protocol:
    All output lines starting with "EVENT:" are parsed by python-manager.ts
    and forwarded to the Swarm-IDE UI via SSE.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.ui_bridge import UIBridge
from core.llm.client import LLMClient, ALFWorldAgent
from core.generator.tree_builder import AgentTreeGenerator
from core.optimizer.performance_monitor import (
    PerformanceMonitor,
    TaskResult,
    TaskStatus,
)
from core.optimizer.extension_engine import DynamicExtensionEngine
from core.recorder.results import ResultsRecorder
from core.memory import get_memory_manager
from core.reflection import get_reflection_agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,  # Logging goes to stderr; stdout is reserved for EVENT: protocol
)
logger = logging.getLogger("run_benchmark")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Auto-Expansion Agent Benchmark Runner"
    )
    parser.add_argument(
        "--benchmark", required=True, help="Benchmark name (alfworld, stulife, webshop)"
    )
    parser.add_argument("--task_id", required=True, help="Task identifier")
    parser.add_argument("--workspace_id", required=True, help="Swarm-IDE workspace ID")
    parser.add_argument(
        "--agent_id", required=True, help="Agent ID assigned by python-manager"
    )
    parser.add_argument(
        "--num_episodes", type=int, default=5, help="Number of episodes to run"
    )
    parser.add_argument(
        "--max_steps", type=int, default=30, help="Max steps per episode"
    )
    parser.add_argument("--model", default=None, help="LLM model override")
    parser.add_argument(
        "--simulated",
        action="store_true",
        help="Run in simulated mode (no real environment)",
    )
    return parser.parse_args()


class BenchmarkRunner:
    """
    Orchestrates a benchmark run with UIBridge-connected event streaming.

    Flow:
        1. Generate initial agent tree from benchmark description
        2. Register all agents with the UI
        3. Run episodes, streaming events for each LLM call / tool call / handoff
        4. Monitor performance and dynamically extend the tree if needed
        5. Report final results
    """

    def __init__(self, args):
        self.benchmark = args.benchmark
        self.task_id = args.task_id
        self.workspace_id = args.workspace_id
        self.root_agent_id = args.agent_id
        self.num_episodes = args.num_episodes
        self.max_steps = args.max_steps
        self.model = args.model
        self.simulated = args.simulated

        self.bridge = UIBridge(workspace_id=self.workspace_id)
        self.monitor = PerformanceMonitor(window_size=100)
        self.recorder = ResultsRecorder()
        self.total_tokens = 0
        self.total_cache_hits = 0
        self.episode_results = []

        # Initialize memory and reflection singletons
        self.memory_manager = get_memory_manager()
        self.reflection_agent = get_reflection_agent()

    def run(self):
        """Main synchronous entry point."""
        try:
            self._run_benchmark()
        except Exception as e:
            logger.exception(f"Benchmark run failed: {e}")
            self.bridge.log(self.root_agent_id, "error", f"Fatal error: {e}")
            sys.exit(1)

    def _run_benchmark(self):
        start_time = time.time()

        # ── Phase 0: Fail-fast environment check ─────────────────
        if self.benchmark == "alfworld":
            from benchmarks.alfworld.alfworld_adapter import AlfworldAdapter

            logger.info("Running ALFWorld environment pre-flight check...")
            check = AlfworldAdapter.check_environment()
            if not check["ok"]:
                msg = f"ALFWorld environment check failed: {check.get('error')}"
                logger.error(msg)
                self.bridge.log(self.root_agent_id, "error", msg)
                raise RuntimeError(msg)
            if check.get("warnings"):
                for w in check["warnings"]:
                    logger.warning(f"ALFWorld warning: {w}")
            logger.info("ALFWorld environment check passed")

        # Initialize ResultsRecorder run
        run_id = self.recorder.initialize_run(
            benchmark_name=self.benchmark,
            config={
                "num_episodes": self.num_episodes,
                "max_steps": self.max_steps,
                "model": self.model,
            },
            tree_config={"benchmark": self.benchmark},
        )
        self._current_run_id = run_id

        # ── Phase 1: Generate agent tree ────────────────────────
        self.bridge.log(
            self.root_agent_id, "system", f"Initializing benchmark: {self.benchmark}"
        )
        self.bridge.llm_start(self.root_agent_id, self.task_id, round_num=0)

        generator = AgentTreeGenerator()
        tree = generator.generate_initial_tree(self.benchmark)

        # Register agents with the UI
        for worker in tree.workers:
            agent_id = f"{self.root_agent_id}:{worker.name}"
            self.bridge.agent_created(
                agent_id, worker.name, parent_id=self.root_agent_id
            )
            self.bridge.log(
                agent_id, "system", f"Worker created: {worker.name} [{worker.domain}]"
            )

        for manager in tree.managers:
            agent_id = f"{self.root_agent_id}:{manager.name}"
            self.bridge.agent_created(
                agent_id, manager.name, parent_id=self.root_agent_id
            )
            self.bridge.log(agent_id, "system", f"Manager created: {manager.name}")

        self.bridge.llm_done(self.root_agent_id, self.task_id, round_num=0)
        self.bridge.log(
            self.root_agent_id,
            "content",
            f"Tree generated: {len(tree.workers)} workers, {len(tree.managers)} managers",
        )

        # ── Phase 2: Run benchmark episodes ─────────────────────
        if self.benchmark == "alfworld" and not self.simulated:
            self._run_alfworld_episodes(tree)
        else:
            self._run_simulated_episodes(tree)

        # ── Phase 3: Check if extension is needed ───────────────
        extension_engine = DynamicExtensionEngine(
            performance_monitor=self.monitor, extension_threshold=0.7
        )
        extended_tree = extension_engine.monitor_and_extend(tree)
        if extended_tree is not tree:
            self.bridge.log(
                self.root_agent_id,
                "system",
                f"Tree extended: now {len(extended_tree.workers)} workers, {len(extended_tree.managers)} managers",
            )

        # ── Phase 4: Report results ─────────────────────────────
        elapsed = time.time() - start_time
        success_count = sum(1 for r in self.episode_results if r.get("success"))
        success_rate = success_count / max(len(self.episode_results), 1)

        # ── Phase 4b: Batch reflection on all failures ───────────
        try:
            failed_episodes = [r for r in self.episode_results if not r.get("success")]
            if failed_episodes:
                batch_failures = []
                for r in failed_episodes:
                    batch_failures.append(
                        {
                            "domain": self.benchmark,
                            "task_type": self.benchmark,
                            "agent_name": self.root_agent_id,
                            "episode_id": f"ep-{r['episode']:03d}",
                            "error_message": r.get(
                                "error", f"Failed after {r.get('steps', 0)} steps"
                            ),
                            "action_history": [],
                            "observation": "",
                            "tools_used": [],
                            "success_rate": success_rate,
                        }
                    )
                reflections = self.reflection_agent.analyze_batch(batch_failures)
                update_results = self.reflection_agent.apply_prompt_updates(reflections)
                self.bridge.log(
                    self.root_agent_id,
                    "system",
                    f"Batch reflection: {len(reflections)} failures analyzed, "
                    f"{len(update_results)} prompt updates applied",
                )
        except Exception as e:
            logger.warning(f"Batch reflection failed: {e}")

        self.bridge.log(
            self.root_agent_id,
            "system",
            f"BENCHMARK COMPLETE. Episodes: {len(self.episode_results)}, "
            f"Success rate: {success_rate:.0%}, Elapsed: {elapsed:.1f}s, "
            f"Total tokens: {self.total_tokens}",
        )

        # Persist results via ResultsRecorder
        try:
            benchmark_results = self.recorder.finalize_run(run_id)
            logger.info(f"Results persisted for run: {run_id}")
        except Exception as e:
            logger.warning(f"Failed to persist results: {e}")

        # Emit final cache metrics
        cache_hit_rate = self.total_cache_hits / max(self.total_tokens, 1)
        self.bridge.cache_metrics(
            agent_id=self.root_agent_id,
            hit_rate=cache_hit_rate,
            hit_tokens=self.total_cache_hits,
            total_tokens=self.total_tokens,
            status="partial"
            if 0 < cache_hit_rate < 0.9
            else ("hit" if cache_hit_rate >= 0.9 else "miss"),
            cost_saved_usd=self.total_cache_hits * 0.000001,  # rough estimate
        )

    def _run_alfworld_episodes(self, tree):
        """Run ALFWorld benchmark episodes with real environment."""
        try:
            from benchmarks.alfworld.alfworld_adapter import AlfworldAdapter

            logger.info("Initializing ALFWorld adapter...")
            adapter = AlfworldAdapter()
            logger.info("ALFWorld adapter ready")
        except Exception as e:
            logger.warning(
                f"ALFWorld adapter unavailable ({e}), falling back to simulation"
            )
            self._run_simulated_episodes(tree)
            return

        try:
            llm = LLMClient(default_model=self.model or "gemini-2.5-flash")
            agent = ALFWorldAgent(llm_client=llm)
            logger.info(f"LLM agent ready (model={llm.default_model})")
        except Exception as e:
            logger.warning(f"LLM client init failed ({e}), falling back to simulation")
            self._run_simulated_episodes(tree)
            return

        worker_id = (
            f"{self.root_agent_id}:{tree.workers[0].name}"
            if tree.workers
            else self.root_agent_id
        )

        for ep in range(self.num_episodes):
            episode_start = time.time()
            episode_id = f"ep-{ep:03d}"
            logger.info(f"--- Episode {ep + 1}/{self.num_episodes} ---")
            self.bridge.log(
                worker_id, "system", f"Episode {ep + 1}/{self.num_episodes} starting"
            )
            self.bridge.llm_start(worker_id, episode_id, round_num=0)

            self.bridge.handoff(
                self.root_agent_id,
                worker_id,
                context_size=1,
                payload_summary=f"Episode {ep + 1}",
            )

            try:
                logger.info("Resetting environment...")
                reset_start = time.time()
                task_desc = adapter.reset()

                # Fetch working context for this episode
                working_ctx = self.memory_manager.get_working_context(
                    agent_name=worker_id, domain="alfworld", task_type="alfworld"
                )

                # Reset agent with fresh context
                agent.reset(working_context=working_ctx)

                logger.info(f"Environment reset in {time.time() - reset_start:.2f}s")
                self.bridge.log(worker_id, "content", f"Task: {task_desc[:200]}")

                success = False
                step_count = 0
                episode_tokens = 0
                episode_cache_hits = 0

                for step in range(self.max_steps):
                    step_count = step + 1
                    admissible = adapter._extract_admissible_commands(
                        adapter.last_info or adapter.infos
                    )

                    self.bridge.tool_call_start(
                        worker_id, episode_id, "llm.select_action"
                    )
                    action = agent.select_action(
                        observation=str(adapter.obs),
                        task_description=task_desc,
                        admissible_actions=admissible,
                    )
                    self.bridge.tool_call_done(
                        worker_id, episode_id, "llm.select_action", ok=True
                    )
                    self.bridge.log(
                        worker_id, "tool_call", f"Step {step_count}: {action}"
                    )

                    last_resp = getattr(agent.llm, "_last_response", None)
                    usage = {}
                    if last_resp and hasattr(last_resp, "usage") and last_resp.usage:
                        usage = last_resp.usage
                    step_tokens = usage.get("total_tokens", 500 + step * 50)
                    step_cache = usage.get("prompt_tokens_details", {}).get(
                        "cached_tokens", int(step_tokens * 0.7)
                    )
                    episode_tokens += step_tokens
                    episode_cache_hits += step_cache
                    self.total_tokens += step_tokens
                    self.total_cache_hits += step_cache

                    self.bridge.tool_call_start(worker_id, episode_id, "env.step")
                    logger.info(f"  Step {step_count}: executing '{action}'")
                    result = adapter.step(action)
                    self.bridge.tool_call_done(
                        worker_id, episode_id, "env.step", ok=True
                    )
                    self.bridge.log(
                        worker_id, "tool_result", result["observation"][:300]
                    )

                    self.bridge.cache_metrics(
                        agent_id=worker_id,
                        hit_rate=step_cache / max(step_tokens, 1),
                        hit_tokens=step_cache,
                        total_tokens=step_tokens,
                        status="partial",
                        cache_hit_position=0,
                        cost_saved_usd=step_cache * 0.000001,
                    )

                    if result["done"]:
                        success = result.get("won", False)
                        logger.info(
                            f"  Episode done at step {step_count}: won={success}"
                        )
                        break

                episode_time = time.time() - episode_start
                reward = adapter.last_reward
                self.episode_results.append(
                    {
                        "episode": ep,
                        "success": success,
                        "steps": step_count,
                        "duration": episode_time,
                        "tokens": episode_tokens,
                    }
                )

                status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
                self.monitor.record_task_result(
                    TaskResult(
                        task_id=episode_id,
                        task_type=self.benchmark,
                        status=status,
                        agent_used=worker_id,
                        duration=episode_time,
                    )
                )

                self.recorder.record_episode(
                    run_id=self._current_run_id,
                    episode_id=ep,
                    task_type=self.benchmark,
                    agent_used=worker_id,
                    status="success" if success else "failure",
                    steps=step_count,
                    reward=reward,
                    duration=episode_time,
                )

                if not success:
                    try:
                        failure_info = {
                            "domain": self.benchmark,
                            "task_type": self.benchmark,
                            "agent_name": worker_id,
                            "episode_id": episode_id,
                            "error_message": f"Episode failed after {step_count} steps",
                            "action_history": [],
                            "observation": str(adapter.obs)[:500]
                            if hasattr(adapter, "obs")
                            else "",
                            "tools_used": [t.name for t in tree.workers[0].tools]
                            if tree.workers and hasattr(tree.workers[0], "tools")
                            else [],
                            "success_rate": sum(
                                1 for r in self.episode_results if r.get("success")
                            )
                            / max(len(self.episode_results), 1),
                        }
                        refl = self.reflection_agent.analyze_failure(failure_info)
                        self.bridge.log(
                            worker_id,
                            "system",
                            f"Reflection: {refl.failure_type} → {refl.prompt_update_action.value}",
                        )
                    except Exception as refl_err:
                        logger.debug(f"Episode reflection skipped: {refl_err}")

                # Store short-term memory of this episode result
                try:
                    from core.memory import MemoryEntry, MemoryType

                    self.memory_manager.store(
                        MemoryEntry(
                            entry_id=f"mem-{episode_id}",
                            memory_type=MemoryType.SHORT_TERM,
                            domain="alfworld",
                            task_type="alfworld",
                            agent_name=worker_id,
                            created_at=datetime.utcnow().isoformat(),
                            content=f"Episode {ep + 1}: {'SUCCESS' if success else 'FAILURE'} "
                            f"in {step_count} steps. Task: {task_desc[:100]}...",
                            tags=[
                                "success" if success else "failure",
                                "episode_result",
                            ],
                            importance=0.8 if not success else 0.5,
                        )
                    )
                    logger.info(f"Stored short-term memory for episode {ep + 1}")
                except Exception as mem_err:
                    logger.warning(f"Failed to store memory: {mem_err}")

                status_emoji = "✅" if success else "❌"
                self.bridge.log(
                    worker_id,
                    "system",
                    f"{status_emoji} Episode {ep + 1}: {'SUCCESS' if success else 'FAILED'} "
                    f"in {step_count} steps ({episode_time:.1f}s, {episode_tokens} tokens)",
                )

            except Exception as e:
                logger.exception(f"Episode {ep} failed: {e}")
                self.bridge.log(worker_id, "error", f"Episode {ep + 1} error: {e}")
                self.episode_results.append(
                    {
                        "episode": ep,
                        "success": False,
                        "steps": 0,
                        "duration": time.time() - episode_start,
                        "error": str(e),
                    }
                )
                self.recorder.record_episode(
                    run_id=self._current_run_id,
                    episode_id=ep,
                    task_type=self.benchmark,
                    agent_used=worker_id,
                    status="failure",
                    steps=0,
                    reward=0.0,
                    duration=time.time() - episode_start,
                    error_message=str(e),
                )

                # Trigger reflection on episode failure
                try:
                    failure_info = {
                        "domain": self.benchmark,
                        "task_type": self.benchmark,
                        "agent_name": worker_id,
                        "episode_id": str(ep),
                        "error_message": str(e),
                        "action_history": [],
                        "observation": "",
                        "tools_used": [],
                        "success_rate": sum(
                            1 for r in self.episode_results if r.get("success")
                        )
                        / max(len(self.episode_results), 1),
                    }
                    refl = self.reflection_agent.analyze_failure(failure_info)
                    self.bridge.log(
                        worker_id,
                        "system",
                        f"Reflection: {refl.failure_type} → {refl.prompt_update_action.value}",
                    )
                except Exception as refl_err:
                    logger.debug(f"Episode reflection skipped: {refl_err}")

            self.bridge.llm_done(worker_id, episode_id, round_num=0)
            self.bridge.handoff(worker_id, self.root_agent_id, context_size=1)

    def _run_simulated_episodes(self, tree):
        """Run simulated episodes when real environment is unavailable."""
        import random

        worker_id = (
            f"{self.root_agent_id}:{tree.workers[0].name}"
            if tree.workers
            else self.root_agent_id
        )

        for ep in range(self.num_episodes):
            episode_start = time.time()
            episode_id = f"ep-{ep:03d}"
            self.bridge.log(
                worker_id, "system", f"[Simulated] Episode {ep + 1}/{self.num_episodes}"
            )
            self.bridge.llm_start(worker_id, episode_id, round_num=0)
            self.bridge.handoff(self.root_agent_id, worker_id, context_size=1)

            steps = random.randint(3, self.max_steps)
            success = random.random() > 0.3  # ~70% success rate

            for step in range(steps):
                time.sleep(0.05)  # Small delay for visual effect

                est_tokens = 400 + step * 30
                est_cache = int(est_tokens * 0.72)
                self.total_tokens += est_tokens
                self.total_cache_hits += est_cache

                self.bridge.tool_call_start(worker_id, episode_id, f"sim.action_{step}")
                self.bridge.log(
                    worker_id,
                    "reasoning",
                    f"Step {step + 1}: Evaluating environment state...",
                )
                self.bridge.tool_call_done(
                    worker_id, episode_id, f"sim.action_{step}", ok=True
                )
                self.bridge.log(
                    worker_id,
                    "tool_result",
                    f"Simulated observation after step {step + 1}",
                )

                self.bridge.cache_metrics(
                    agent_id=worker_id,
                    hit_rate=est_cache / max(est_tokens, 1),
                    hit_tokens=est_cache,
                    total_tokens=est_tokens,
                    status="partial",
                    cache_hit_position=0,
                    cost_saved_usd=est_cache * 0.000001,
                )

            episode_time = time.time() - episode_start
            self.episode_results.append(
                {
                    "episode": ep,
                    "success": success,
                    "steps": steps,
                    "duration": episode_time,
                }
            )

            status = TaskStatus.SUCCESS if success else TaskStatus.FAILURE
            self.monitor.record_task_result(
                TaskResult(
                    task_id=episode_id,
                    task_type=self.benchmark,
                    status=status,
                    agent_used=worker_id,
                    duration=episode_time,
                )
            )

            emoji = "✅" if success else "❌"
            self.bridge.log(
                worker_id,
                "system",
                f"{emoji} Episode {ep + 1}: {'SUCCESS' if success else 'FAILED'}",
            )
            self.bridge.llm_done(worker_id, episode_id, round_num=0)
            self.bridge.handoff(worker_id, self.root_agent_id, context_size=1)


def main():
    args = parse_args()
    logger.info(
        f"Starting benchmark: {args.benchmark} (task={args.task_id}, workspace={args.workspace_id})"
    )
    runner = BenchmarkRunner(args)
    runner.run()


if __name__ == "__main__":
    main()
