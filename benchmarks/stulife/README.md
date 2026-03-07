# StuLife Benchmark Adapter

Thin adapter for integrating StuLife (Campus Life Benchmark) with the A2S framework.

## Architecture

This adapter uses a **薄层封装 (thin wrapper)** approach:
- Directly imports and uses StuLife source code from `benchmarks/stulife_source/`
- Provides simple `reset()` and `step()` interface
- No modification to StuLife source code required
- Easy to maintain when StuLife source is updated

## Usage

```python
from benchmarks.stulife import StuLifeAdapter

# Initialize adapter
adapter = StuLifeAdapter()

# Get available tasks
tasks = adapter.get_available_tasks()
print(f"Available tasks: {tasks}")

# Reset to a specific task
result = adapter.reset(task_id="quiz_test")
print(f"Task: {result['task_id']}")
print(f"Observation: {result['observation']}")

# Execute actions
result = adapter.step("I will answer: B")
print(f"Done: {result['done']}")
print(f"Success: {result['success']}")

# Close adapter
adapter.close()
```

## Testing

Run the test script to verify the adapter works:

```bash
conda activate stulife
python benchmarks/stulife/test_adapter.py
```

## Task Types

StuLife includes 6 task categories:
- **Navigation**: Campus navigation with map and geography tools
- **Email**: Email management (send, search, read)
- **Course**: Course registration with prerequisites and conflicts
- **Calendar**: Calendar event management
- **Reservation**: Room/resource reservation
- **Quiz**: In-class quiz questions

## Integration with A2S

The adapter provides a simple interface that can be used by A2S agents:

1. **Task Loading**: Automatically loads tasks from StuLife data directory
2. **Session Management**: Handles StuLife's Session and ChatHistory internally
3. **Action Execution**: Translates agent actions to StuLife's interact() calls
4. **Evaluation**: Returns success/failure status after task completion

## Modifying StuLife Source

To modify StuLife benchmark (e.g., add parallel execution):

1. Edit files in `benchmarks/stulife_source/Stulife/src/`
2. The adapter will automatically use the updated code
3. No need to modify the adapter itself

## Files

- `stulife_adapter.py`: Main adapter implementation
- `test_adapter.py`: Test script
- `benchmark_intro.yaml`: Benchmark metadata for A2S
- `__init__.py`: Package exports
