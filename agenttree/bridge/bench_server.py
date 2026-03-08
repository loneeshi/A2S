"""
Benchmark Bridge Server — HTTP/JSON wrapper for ALFWorld & StuLife environments.

Exposes a simple REST API so the TypeScript agenttree runtime can drive
real benchmark environments from Node.js.

Endpoints:
    POST /reset          → Reset the environment; returns task description
    POST /step           → Execute one action; returns observation + done + won
    GET  /status         → Current environment state
    POST /shutdown       → Gracefully shut down the server

Usage:
    python bridge/bench_server.py --benchmark alfworld --port 8765
    python bridge/bench_server.py --benchmark stulife  --port 8765

The TypeScript side connects via BenchmarkBridge (src/bridge/client.ts).
"""

import argparse
import json
import logging
import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bench_server] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bench_server")

# ---------- Environment adapters ----------

_env = None
_benchmark = None
_episode = 0


def init_alfworld(config_path=None, split="train"):
    """Initialize ALFWorld via the existing AlfworldAdapter."""
    global _env
    from benchmarks.alfworld.alfworld_adapter import AlfworldAdapter

    logger.info("Initializing ALFWorld adapter...")
    _env = AlfworldAdapter(config_path=config_path, train_eval=split)
    logger.info("ALFWorld adapter ready.")


def init_stulife(config_path=None):
    """
    Initialize StuLife environment using our StuLifeAdapter.
    """
    global _env
    try:
        from benchmarks.stulife.stulife_adapter import StuLifeAdapter
        from benchmarks.stulife.logging import LoggingCoordinator
        from datetime import datetime

        logger.info("Initializing StuLife adapter...")
        _env = StuLifeAdapter()

        # Initialize three-tier logging
        run_id = f"stulife_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S-%f')}"
        output_dir = PROJECT_ROOT / "results" / "stulife"
        output_dir.mkdir(parents=True, exist_ok=True)

        _env._logging_coordinator = LoggingCoordinator(
            run_id=run_id,
            benchmark="stulife",
            model="gpt-4o-mini",  # Will be updated from TypeScript
            output_dir=output_dir
        )

        logger.info(f"StuLife adapter ready with {len(_env.get_available_tasks())} tasks")
        logger.info(f"Three-tier logging initialized: {run_id}")
    except Exception as e:
        logger.error(f"Failed to initialize StuLife adapter: {e}")
        logger.warning("Falling back to stub environment")
        _env = StuLifeStub()


class StuLifeStub:
    """Minimal StuLife stub that speaks the same protocol as CampusEnvironment."""

    def __init__(self):
        self._location = "dormitory"
        self._time = "Week 1, Monday 08:00"
        self._done = False
        self._step = 0
        self._task = "Navigate to the library and reserve a study room."

    def reset(self):
        self._location = "dormitory"
        self._time = "Week 1, Monday 08:00"
        self._done = False
        self._step = 0
        return self._task

    def step(self, action: str):
        self._step += 1
        obs = f"[stub] Executed: {action} (step {self._step})"

        if "walk_to" in action.lower() and "library" in action.lower():
            self._location = "library"
            obs = "You walked to the Library. You are now at the Library entrance."

        if "reserve" in action.lower() or "finish" in action.lower():
            self._done = True
            obs += "\n[System]: Task completed."

        return {
            "observation": obs,
            "done": self._done,
            "won": self._done,
            "reward": 1.0 if self._done else 0.0,
            "admissible_commands": [],
        }


# ---------- Unified wrappers ----------


def env_reset():
    global _episode
    _episode += 1

    if _benchmark == "alfworld":
        raw = _env.reset()
        # The adapter returns str(obs) which may be a tuple repr like "('...',)"
        # Ensure we get a clean string.
        if isinstance(raw, (list, tuple)):
            task = str(raw[0]) if raw else ""
        else:
            task = str(raw)
        # Strip Python tuple repr wrapper if present
        if task.startswith("('") and task.endswith("',)"):
            task = task[2:-3]
        elif task.startswith('("') and task.endswith('",)'):
            task = task[2:-3]
        admissible = _env._extract_admissible_commands(_env.infos)
        return {
            "task": task,
            "episode": _episode,
            "admissible_commands": admissible,
        }
    elif _benchmark == "stulife":
        # Get available tasks and select one
        available_tasks = _env.get_available_tasks()
        task_id = available_tasks[_episode % len(available_tasks)]

        # Reset with specific task
        reset_result = _env.reset(task_id=task_id)
        task = reset_result["observation"]

        # Start logging for this episode
        if hasattr(_env, '_logging_coordinator'):
            episode_id = f"ep-{_episode:03d}"
            _env._logging_coordinator.start_episode(
                episode_id=episode_id,
                task_id=task_id,
                step=0
            )
            logger.info(f"Started logging for episode {episode_id}, task {task_id}")

        return {"task": task, "episode": _episode, "task_id": task_id, "admissible_commands": []}
    else:
        return {"error": f"Unknown benchmark: {_benchmark}"}


def env_step(action: str):
    if _benchmark == "alfworld":
        result = _env.step(action)
        return result
    elif _benchmark == "stulife":
        result = _env.step(action)

        # Update step counter in logging
        if hasattr(_env, '_logging_coordinator') and hasattr(_env, '_step_counter'):
            _env._step_counter = getattr(_env, '_step_counter', 0) + 1
            _env._logging_coordinator.update_step(_env._step_counter)

        # Handle result format
        if isinstance(result, dict):
            # Check if episode is done
            if result.get("done", False):
                # End episode logging
                if hasattr(_env, '_logging_coordinator'):
                    session = _env.get_current_session()
                    episode_id = f"ep-{_episode:03d}"
                    _env._logging_coordinator.end_episode(
                        episode_id=episode_id,
                        session=session
                    )
                    logger.info(f"Ended logging for episode {episode_id}")
            return result
        # CampusEnvironment may return tuple (obs, reward, done, info)
        obs, reward, done, info = result

        # End episode logging if done
        if done and hasattr(_env, '_logging_coordinator'):
            session = _env.get_current_session()
            episode_id = f"ep-{_episode:03d}"
            _env._logging_coordinator.end_episode(
                episode_id=episode_id,
                session=session
            )
            logger.info(f"Ended logging for episode {episode_id}")

        return {
            "observation": str(obs),
            "done": done,
            "won": info.get("success", False) if isinstance(info, dict) else False,
            "reward": reward,
            "admissible_commands": [],
        }
    else:
        return {"error": f"Unknown benchmark: {_benchmark}"}


def env_status():
    info = {"benchmark": _benchmark, "episode": _episode}
    if _benchmark == "alfworld" and _env:
        info["done"] = _env.is_done
        info["last_reward"] = _env.last_reward
    return info


# ---------- HTTP handler ----------


class BridgeHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler: POST JSON body → JSON response."""

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_GET(self):
        if self.path == "/status":
            self._send_json(env_status())
        elif self.path == "/health":
            self._send_json({"ok": True, "benchmark": _benchmark})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            body = self._read_body()

            if self.path == "/reset":
                result = env_reset()
                self._send_json(result)

            elif self.path == "/step":
                action = body.get("action", "")
                if not action:
                    self._send_json({"error": "Missing 'action' field"}, 400)
                    return
                result = env_step(action)
                self._send_json(result)

            elif self.path == "/shutdown":
                # Finalize logging before shutdown
                if _benchmark == "stulife" and _env and hasattr(_env, '_logging_coordinator'):
                    try:
                        result = _env._logging_coordinator.finalize()
                        logger.info(f"✅ Three-tier logging finalized:")
                        logger.info(f"   Tier 1: {result['tier1_runs_json']}")
                        logger.info(f"   Tier 2: {result['tier2_worker_actions']}")
                        logger.info(f"   Tier 3: {result['tier3_api_calls']}")
                        logger.info(f"   Sessions: {result['session_count']}")
                        logger.info(f"   Worker actions: {result['worker_action_count']}")
                        logger.info(f"   API calls: {result['api_call_count']}")
                    except Exception as e:
                        logger.error(f"Failed to finalize logging: {e}")

                self._send_json({"ok": True, "message": "Shutting down..."})
                import threading

                threading.Thread(target=self.server.shutdown, daemon=True).start()

            else:
                self._send_json({"error": "Not found"}, 404)

        except Exception as e:
            logger.exception(f"Request error: {e}")
            self._send_json({"error": str(e), "traceback": traceback.format_exc()}, 500)

    def log_message(self, format, *args):
        logger.debug(f"{self.client_address[0]} - {format % args}")


# ---------- Main ----------


def main():
    global _benchmark

    parser = argparse.ArgumentParser(description="Benchmark Bridge Server")
    parser.add_argument(
        "--benchmark",
        required=True,
        choices=["alfworld", "stulife"],
        help="Which benchmark to serve",
    )
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--split", default="train", help="ALFWorld split")
    parser.add_argument("--config", default=None, help="Config file path")
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Skip N episodes at start (for parallel sharding)",
    )
    args = parser.parse_args()

    _benchmark = args.benchmark

    if _benchmark == "alfworld":
        init_alfworld(config_path=args.config, split=args.split)
    elif _benchmark == "stulife":
        init_stulife(config_path=args.config)

    # Skip N episodes so parallel workers get disjoint game sequences
    if args.skip > 0:
        logger.info(f"Skipping {args.skip} episodes for parallel sharding...")
        for _ in range(args.skip):
            env_reset()
        logger.info(f"Skipped to episode {_episode}")

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = ReusableHTTPServer((args.host, args.port), BridgeHandler)
    logger.info(f"Bridge server ready: http://{args.host}:{args.port} ({_benchmark})")
    logger.info("Endpoints: POST /reset, POST /step, GET /status, POST /shutdown")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
