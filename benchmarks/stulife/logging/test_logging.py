"""
Test script for three-tier logging system

Tests each component independently and together.
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from benchmarks.stulife.logging import LoggingCoordinator
from benchmarks.stulife.logging.context import LoggingContext, set_logging_context


def test_context():
    """Test context management"""
    print("Testing context management...")

    ctx = LoggingContext(
        episode_id="ep-000",
        task_id="task-123",
        step=1,
        worker_id="test_worker",
        run_id="test_run",
    )

    set_logging_context(ctx)
    print("✅ Context set successfully")


def test_coordinator():
    """Test logging coordinator"""
    print("\nTesting logging coordinator...")

    # Create temporary output directory
    output_dir = Path("/tmp/stulife_logging_test")
    output_dir.mkdir(exist_ok=True)

    # Initialize coordinator
    coordinator = LoggingCoordinator(
        run_id="test_run_001",
        benchmark="stulife",
        model="gpt-4o-mini",
        output_dir=output_dir,
    )

    print("✅ Coordinator initialized")

    # Start episode
    coordinator.start_episode(episode_id="ep-000", task_id="task-001", step=0)
    print("✅ Episode started")

    # Log worker action
    coordinator.log_worker_action(
        task_summary="Navigate to library",
        action_taken="go to library",
        decision_rationale="Need to reach library for studying",
        tools_used=[],
        duration_ms=1234.5,
    )
    print("✅ Worker action logged")

    # Trace API call
    coordinator.trace_api_call(
        request={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Test prompt"}],
            "temperature": 0.7,
        },
        response={"content": "Test response", "finish_reason": "stop"},
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        cache_info={"cache_read_input_tokens": 80},
        latency_ms=500.0,
    )
    print("✅ API call traced")

    # Update step
    coordinator.update_step(2)
    print("✅ Step updated")

    # End episode (without session for now)
    coordinator.end_episode(episode_id="ep-000", session=None)
    print("✅ Episode ended")

    # Get stats
    stats = coordinator.get_stats()
    print(f"✅ Stats: {stats}")

    # Finalize
    result = coordinator.finalize()
    print(f"✅ Finalized: {result}")

    # Verify files exist
    worker_actions_file = output_dir / "test_run_001_worker_actions.json"
    api_calls_file = output_dir / "test_run_001_api_calls.json"

    assert worker_actions_file.exists(), "Worker actions file not created"
    assert api_calls_file.exists(), "API calls file not created"

    # Verify content
    with open(worker_actions_file) as f:
        worker_data = json.load(f)
        assert len(worker_data["worker_actions"]) == 1
        print(f"✅ Worker actions file verified: {len(worker_data['worker_actions'])} actions")

    with open(api_calls_file) as f:
        api_data = json.load(f)
        assert len(api_data["api_calls"]) == 1
        print(f"✅ API calls file verified: {len(api_data['api_calls'])} calls")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_context()
    test_coordinator()
