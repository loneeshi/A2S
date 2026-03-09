#!/usr/bin/env bash
#
# Start N bridge servers for parallel benchmark runs.
#
# Usage:
#   ./bridge/start_servers.sh                    # 3 servers (default)
#   ./bridge/start_servers.sh 5                  # 5 servers
#   ./bridge/start_servers.sh 3 8800             # 3 servers starting at port 8800
#   ./bridge/start_servers.sh 3 8765 stulife     # 3 servers for stulife
#
# Stop all:
#   ./bridge/start_servers.sh stop
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEM_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$SYSTEM_DIR/runs/.pids"

# ─── Stop mode ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "stop" ]]; then
  if [[ -d "$PID_DIR" ]]; then
    echo "Stopping bridge servers..."
    for pidfile in "$PID_DIR"/*.pid; do
      [[ -f "$pidfile" ]] || continue
      pid=$(cat "$pidfile")
      port=$(basename "$pidfile" .pid | sed 's/server_//')
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "  Stopped server on port $port (pid $pid)"
      else
        echo "  Server on port $port (pid $pid) already stopped"
      fi
      rm -f "$pidfile"
    done
    rmdir "$PID_DIR" 2>/dev/null || true
  else
    echo "No running servers found."
  fi
  exit 0
fi

# ─── Start mode ─────────────────────────────────────────────────────────
NUM_SERVERS="${1:-3}"
BASE_PORT="${2:-8765}"
BENCHMARK="${3:-alfworld}"
SPLIT="${4:-train}"
EPISODES_PER_WORKER="${5:-0}"

echo "═══ Starting $NUM_SERVERS bridge servers ═══"
echo "  Benchmark: $BENCHMARK"
echo "  Split:     $SPLIT"
echo "  Ports:     $BASE_PORT..$((BASE_PORT + NUM_SERVERS - 1))"
echo ""

mkdir -p "$PID_DIR"

# Check if any requested ports are already in use
for i in $(seq 0 $((NUM_SERVERS - 1))); do
  port=$((BASE_PORT + i))
  if lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "WARNING: Port $port already in use. Skipping."
    continue
  fi

  echo -n "  Starting server $i on port $port (skip $((i * EPISODES_PER_WORKER)))... "

  python "$SCRIPT_DIR/bench_server.py" \
    --benchmark "$BENCHMARK" \
    --port "$port" \
    --split "$SPLIT" \
    --skip "$((i * EPISODES_PER_WORKER))" \
    > "$SYSTEM_DIR/runs/server_${port}.log" 2>&1 &

  server_pid=$!
  echo "$server_pid" > "$PID_DIR/server_${port}.pid"
  echo "pid $server_pid"
done

# Wait for all servers to become healthy
echo ""
echo -n "  Waiting for servers to be ready"
MAX_WAIT=30
for i in $(seq 0 $((NUM_SERVERS - 1))); do
  port=$((BASE_PORT + i))
  pidfile="$PID_DIR/server_${port}.pid"
  [[ -f "$pidfile" ]] || continue

  waited=0
  while ! curl -sf "http://localhost:${port}/health" >/dev/null 2>&1; do
    sleep 1
    waited=$((waited + 1))
    echo -n "."
    if [[ $waited -ge $MAX_WAIT ]]; then
      echo ""
      echo "  ERROR: Server on port $port not ready after ${MAX_WAIT}s"
      echo "  Check log: runs/server_${port}.log"
      exit 1
    fi
  done
done

echo " OK"
echo ""
echo "All $NUM_SERVERS servers ready."
echo "To stop: ./bridge/start_servers.sh stop"
echo ""
echo "Run benchmark:"
echo "  npx tsx examples/run_benchmark_parallel.ts \\"
echo "    --benchmark $BENCHMARK --episodes 10 --parallel $NUM_SERVERS \\"
echo "    --base-port $BASE_PORT --no-auto-start --extend --evolve"
