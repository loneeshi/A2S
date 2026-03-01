#!/bin/bash
# Test script wrapper that activates conda environment

# Conda environment name
CONDA_ENV="skilltree_py311"

# Project directory
PROJECT_DIR="/Users/dp/Agent_research/design/auto_expansion_agent"
TEST_SCRIPT="$PROJECT_DIR/scripts/test_alfworld_real.py"

# Number of episodes (can be overridden with argument)
NUM_EPISODES=${1:-3}

echo "========================================="
echo "  ALFWorld Test Runner"
echo "========================================="
echo ""
echo "Conda environment: $CONDA_ENV"
echo "Episodes: $NUM_EPISODES"
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda command not found"
    echo "Please make sure conda is installed and in your PATH"
    exit 1
fi

# Activate conda environment and run test
echo "Activating conda environment: $CONDA_ENV"
echo ""

# Run with conda
conda run -n $CONDA_ENV python $TEST_SCRIPT --num_episodes $NUM_EPISODES

exit_code=$?

echo ""
echo "========================================="
if [ $exit_code -eq 0 ]; then
    echo "✅ Test completed successfully"
else
    echo "❌ Test failed with exit code: $exit_code"
fi
echo "========================================="

exit $exit_code
