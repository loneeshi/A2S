# ALFWorld Integration Guide

This guide explains how to integrate and test the auto-expansion agent framework with the real ALFWorld environment.

## Prerequisites

- Conda environment: `skilltree_py311`
- Python 3.11

## Installation Steps

### 1. Activate Conda Environment

```bash
conda activate skilltree_py311
```

### 2. Install ALFWorld

```bash
pip install alfworld
```

Or use the setup script:

```bash
bash scripts/setup_alfworld.sh
```

### 3. Verify Installation

```python
python -c "import alfworld; print('ALFWorld installed successfully')"
```

## Running Tests

### Option 1: Simulated Test (No ALFWorld Required)

```bash
python scripts/test_alfworld.py
```

This runs simulated episodes without requiring ALFWorld installation.

### Option 2: Real ALFWorld Test

```bash
# Activate conda environment first
conda activate skilltree_py311

# Run with default settings (5 episodes, train split)
python scripts/test_alfworld_real.py

# Run with custom settings
python scripts/test_alfworld_real.py --num_episodes 10 --split valid_in_distribution
```

## Test Options

- `--num_episodes`: Number of episodes to run (default: 5)
- `--split`: Data split to use
  - `train`: Training tasks
  - `valid_in_distribution`: Validation tasks (in distribution)
  - `test_in_distribution`: Test tasks (in distribution)

## Expected Output

The test will:

1. **Initialize ALFWorld Environment**
   - Load ALFWorld library
   - Create environment instance

2. **Generate Agent Tree**
   - Read ALFWorld benchmark intro
   - Create workers and managers
   - Build cache-optimized prompts

3. **Run Episodes**
   - Execute tasks in real ALFWorld environment
   - Record performance metrics
   - Track success/failure rates

4. **Performance Analysis**
   - Calculate overall success rate
   - Identify underperforming agents
   - Detect difficult task types

5. **Dynamic Extension** (if needed)
   - Automatically add specialized workers
   - Extend tree based on performance

## Example Results

```
================================================================================
  Phase 4: Run Real ALFWorld Episodes
================================================================================

--- Episode 1/5 ---
Task: Put a clean apple in the fridge.
Observation: You are in a kitchen. You see: apple, fridge, sink, counter...
Steps: 12, Reward: 1.00, Success: True

--- Episode 2/5 ---
Task: Go to the bedroom and find the alarm clock.
Observation: You are in a hallway. You can go to: bedroom, bathroom...
Steps: 8, Reward: 0.00, Success: False

...

✅ Completed 5 real episodes
Success rate: 3/5 (60.0%)

================================================================================
  Summary
================================================================================

🎉 Real ALFWorld test completed!

Results:
   Episodes run: 5
   Success rate: 60.0%
   Final workers: 5
   Final managers: 2
```

## Troubleshooting

### ALFWorld Not Installed

```bash
❌ ALFWorld not installed!
```

**Solution**: Install ALFWorld in conda environment
```bash
conda activate skilltree_py311
pip install alfworld
```

### Data Files Missing

```
⚠️  ALFWorld data directory not found
```

**Solution**: Download ALFWorld data files. See [ALFWorld GitHub](https://github.com/alfworld/alfworld) for instructions.

### Import Errors

```
ModuleNotFoundError: No module named 'alfworld'
```

**Solution**: Make sure you're in the correct conda environment
```bash
conda activate skilltree_py311
which python  # Should show path to skilltree_py311 environment
```

## Performance Metrics

The framework tracks:

- **Task Success Rate**: Percentage of successfully completed tasks
- **Agent Performance**: Success rate per worker agent
- **Task Type Difficulty**: Success rate per task type
- **Extension Events**: When and why new workers were added

## Next Steps

1. **Increase Episodes**: Run more episodes for reliable statistics
2. **Fine-tune Thresholds**: Adjust extension threshold based on results
3. **Add More Benchmarks**: Integrate WebShop, BabyAI, etc.
4. **Compare Performance**: Benchmark against baseline agents

## Contact

For issues or questions, refer to the main README.md.
