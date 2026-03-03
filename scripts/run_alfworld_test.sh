#!/bin/bash
# Test script for ALFWorld with LLM agent

# Check if API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ OPENAI_API_KEY not set!"
    echo ""
    echo "Please set your API key:"
    echo "  export OPENAI_API_KEY='your_api_key_here'"
    echo "  export OPENAI_BASE_URL='https://az.gptplus5.com/v1'"
    echo ""
    exit 1
fi

echo "✅ API key found"
echo "Base URL: ${OPENAI_BASE_URL:-https://api.openai.com/v1}"
echo ""

# Run test
/opt/anaconda3/envs/skilltree_py311/bin/python /Users/dp/Agent_research/design/auto_expansion_agent/scripts/test_alfworld_real.py --num_episodes 3 --split train
