
#!/bin/bash
# ALFWorld Smoke Run — minimal validation of the full benchmark pipeline
#
# Usage:
#   bash scripts/smoke_run.sh
#   bash scripts/smoke_run.sh --simulated   # skip real env, use simulated episodes
#
# Environment variables:
#   OPENAI_API_KEY      — Required for LLM calls
#   OPENAI_BASE_URL     — API endpoint (default: https://api.openai.com/v1)
#   ALFWORLD_DATA       — Path to ALFWorld dataset (required for real env)
#   LLM_MODEL           — Model override (default: gemini-2.5-flash)
#   PYTHON              — Python interpreter (default: auto-detect)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# --- Detect Python ---
if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif command -v /opt/anaconda3/envs/skilltree_py311/bin/python &>/dev/null; then
    PY="/opt/anaconda3/envs/skilltree_py311/bin/python"
elif command -v python3 &>/dev/null; then
    PY="python3"
else
    PY="python"
fi
echo "Python: $PY"

# --- Load .env if present ---
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo "Loaded .env"
fi

# --- Check API key ---
if [ -z "${OPENAI_API_KEY:-}" ]; then
    echo "ERROR: OPENAI_API_KEY not set."
    echo "  export OPENAI_API_KEY='sk-...'"
    exit 1
fi
echo "API key: ...${OPENAI_API_KEY: -4}"
echo "Base URL: ${OPENAI_BASE_URL:-https://api.openai.com/v1}"

# --- Choose benchmark mode ---
BENCHMARK="alfworld"
SIMULATED_FLAG=""
if [[ "${1:-}" == "--simulated" ]]; then
    SIMULATED_FLAG="--simulated"
    echo "Mode: SIMULATED (no real ALFWorld env needed)"
else
    echo "Mode: REAL ALFWorld environment"
    echo "  ALFWORLD_DATA: ${ALFWORLD_DATA:-<not set>}"
fi

echo ""
echo "=== Smoke Run: 2 episodes, max 15 steps ==="
echo ""

# --- Run benchmark ---
TASK_ID="smoke-$(date +%s)"
WORKSPACE_ID="smoke-ws"
AGENT_ID="smoke-agent"

exec "$PY" "$PROJECT_ROOT/scripts/run_benchmark.py" \
    --benchmark "$BENCHMARK" \
    --task_id "$TASK_ID" \
    --workspace_id "$WORKSPACE_ID" \
    --agent_id "$AGENT_ID" \
    --num_episodes 2 \
    --max_steps 15 \
    $SIMULATED_FLAG
