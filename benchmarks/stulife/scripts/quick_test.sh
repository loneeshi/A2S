#!/bin/bash
# 快速测试脚本 - 运行 2 episodes 验证系统

set -e

echo "=== Quick Test: 2 Episodes ==="
echo ""

# 1. 清理
pkill -9 -f "run_benchmark" 2>/dev/null || true
pkill -9 -f "bench_server" 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
sleep 2

# 2. 编译
cd /Users/a86135/Desktop/A2S/A2S/agenttree
npm run build > /dev/null 2>&1

# 3. 运行
cd /Users/a86135/Desktop/A2S/A2S
export $(cat .env | grep -v '^#' | xargs)
cd agenttree

npx tsx examples/run_benchmark.ts \
    --benchmark stulife \
    --episodes 2 \
    --max-steps 30

# 4. 检查结果
LATEST=$(ls -td ../results/stulife/stulife_* 2>/dev/null | head -1)
echo ""
echo "Results: $LATEST"
SESSION_COUNT=$(cat "$LATEST/tier1_runs.json" | jq '. | length' 2>/dev/null || echo "0")
echo "Sessions: $SESSION_COUNT"

if [ "$SESSION_COUNT" -gt "0" ]; then
    echo "✓ Sessions saved successfully!"
    cat "$LATEST/tier1_runs.json" | jq '.[0] | {sample_index, sample_status, finish_reason}' 2>/dev/null || true
else
    echo "❌ No sessions saved!"
fi
