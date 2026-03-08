# Three-Tier Logging System for StuLife Benchmark

This directory contains a comprehensive three-tier logging system for the StuLife benchmark, designed to capture different levels of detail for analysis, debugging, and metric calculation.

## Overview

The logging system captures three distinct layers of information:

1. **Tier 1 - Benchmark Layer**: StuLife native `runs.json` format for metric calculation
2. **Tier 2 - Abstract Layer**: High-level worker behavior decisions for quick analysis
3. **Tier 3 - Detailed Layer**: Complete API call context windows for debugging

## Architecture

```
benchmarks/stulife/logging/
├── __init__.py              # Package exports
├── context.py               # Thread-local context management
├── session_collector.py     # Tier 1: Session collection
├── worker_logger.py         # Tier 2: Worker behavior logging
├── api_tracer.py           # Tier 3: API call tracing
├── coordinator.py          # Central coordinator
├── agent_wrapper.py        # TrackedStuLifeAgent wrapper
└── test_logging.py         # Unit tests
```

## Components

### Context Management (`context.py`)

Uses Python's `contextvars` to pass episode_id, task_id, step, and worker_id through the call stack without explicit parameter passing.

```python
from benchmarks.stulife.logging.context import LoggingContext, set_logging_context

ctx = LoggingContext(
    episode_id="ep-000",
    task_id="task-123",
    step=1,
    worker_id="stulife_worker"
)
set_logging_context(ctx)
```

### Tier 1: Session Collector (`session_collector.py`)

Collects StuLife `Session` objects and generates `runs.json` in the native format compatible with `calculate_stulife_metrics.py`.

**Output**: `benchmarks/stulife_source/Stulife/result/{model_name}/runs.json`

### Tier 2: Worker Logger (`worker_logger.py`)

Records high-level worker manager behavior decisions for quick scanning and analysis.

**Output**: `results/stulife/{run_id}_worker_actions.json`

**Format**:
```json
{
  "run_id": "stulife_2026-03-08T10-00-00-000000",
  "model": "gpt-4o-mini",
  "worker_actions": [
    {
      "timestamp": "2026-03-08T10:00:01.123",
      "episode_id": "ep-000",
      "step": 1,
      "worker_id": "stulife_worker",
      "task_summary": "Navigate to library",
      "action_taken": "go to library",
      "decision_rationale": "Need to reach library for studying",
      "tools_used": [],
      "duration_ms": 1234
    }
  ]
}
```

### Tier 3: API Call Tracer (`api_tracer.py`)

Records complete API call context windows including full request/response data, token usage, and cache information.

**Output**: `results/stulife/{run_id}_api_calls.json`

**Format**:
```json
{
  "run_id": "stulife_2026-03-08T10-00-00-000000",
  "api_calls": [
    {
      "call_id": "call-001",
      "timestamp": "2026-03-08T10:00:01.123",
      "episode_id": "ep-000",
      "step": 1,
      "worker_id": "stulife_worker",
      "request": {
        "model": "gpt-4o-mini",
        "messages": [...],
        "temperature": 0.7,
        "max_tokens": 1000
      },
      "response": {
        "content": "...",
        "finish_reason": "stop"
      },
      "usage": {
        "prompt_tokens": 1234,
        "completion_tokens": 567,
        "total_tokens": 1801
      },
      "cache_info": {
        "cache_read_input_tokens": 1200
      },
      "latency_ms": 1234,
      "error": null
    }
  ]
}
```

### Logging Coordinator (`coordinator.py`)

Central coordinator that manages the lifecycle of all three logging tiers and ensures consistency.

```python
from benchmarks.stulife.logging import LoggingCoordinator

coordinator = LoggingCoordinator(
    run_id="stulife_2026-03-08T10-00-00-000000",
    benchmark="stulife",
    model="gpt-4o-mini",
    output_dir=Path("results/stulife")
)

# Start episode
coordinator.start_episode(episode_id="ep-000", task_id="task-001")

# Log worker action
coordinator.log_worker_action(
    task_summary="Navigate to library",
    action_taken="go to library",
    decision_rationale="Need to reach library",
    duration_ms=1234
)

# Trace API call
coordinator.trace_api_call(
    request={...},
    response={...},
    usage={...}
)

# End episode
coordinator.end_episode(episode_id="ep-000", session=session_obj)

# Finalize and save all logs
coordinator.finalize()
```

### Tracked Agent Wrapper (`agent_wrapper.py`)

`TrackedStuLifeAgent` wraps the standard `StuLifeAgent` to intercept API calls and log them without modifying core code.

```python
from benchmarks.stulife.logging.agent_wrapper import TrackedStuLifeAgent

agent = TrackedStuLifeAgent(
    llm_client=llm_client,
    model="gpt-4o-mini",
    coordinator=coordinator
)

# Use like normal StuLifeAgent
action = agent.select_action(
    observation=observation,
    task_description=task_description
)
```

## Integration

The logging system is integrated into `scripts/run_benchmark.py` in the `_run_stulife_episodes()` method:

1. Initialize `LoggingCoordinator`
2. Use `TrackedStuLifeAgent` instead of `StuLifeAgent`
3. Call `coordinator.start_episode()` at episode start
4. Call `coordinator.update_step()` at each step
5. Call `coordinator.end_episode()` with session object at episode end
6. Call `coordinator.finalize()` after all episodes complete

## Output Files

After running the benchmark, you'll find:

```
benchmarks/stulife_source/Stulife/result/{model_name}/
└── runs.json                                    # Tier 1: Native format

results/stulife/
├── {run_id}_worker_actions.json                 # Tier 2: Worker behavior
├── {run_id}_api_calls.json                      # Tier 3: API calls
├── {run_id}_detailed.log                        # Existing: Text log
├── {run_id}_detailed.json                       # Existing: JSON log
├── {run_id}.json                                # Existing: Results
└── {run_id}_summary.txt                         # Existing: Summary
```

## Testing

Run the unit tests:

```bash
python -m benchmarks.stulife.logging.test_logging
```

## Usage Example

```bash
# Run StuLife benchmark with three-tier logging
python scripts/run_benchmark.py \
    --benchmark stulife \
    --num-episodes 5 \
    --max-steps 10 \
    --model gpt-4o-mini
```

The three-tier logs will be automatically generated and saved.

## Design Principles

1. **Non-invasive**: No modifications to `core/` directory code
2. **Wrapper pattern**: Uses agent wrapper to intercept API calls
3. **Context propagation**: Thread-local context for automatic metadata passing
4. **Backward compatible**: Preserves existing logging functionality
5. **Error resilient**: Logging failures don't crash the benchmark
6. **Version control friendly**: JSON format with clear structure

## Future Enhancements

- Add compression for large log files
- Implement streaming writes for long runs
- Add configuration options to enable/disable specific tiers
- Create analysis tools for log files
- Add visualization dashboard for logged data
