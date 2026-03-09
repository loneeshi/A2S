#!/bin/bash
# StuLife Benchmark 运行脚本
# 用法: ./run_benchmark.sh [episodes] [max_steps]
# 示例: ./run_benchmark.sh 10 50

set -e

EPISODES=${1:-10}
MAX_STEPS=${2:-50}

echo "=========================================="
echo "  StuLife Benchmark Runner"
echo "=========================================="
echo "Episodes: $EPISODES"
echo "Max Steps: $MAX_STEPS"
echo ""

# 1. 清理旧进程和端口
echo "=== Cleanup ==="
pkill -9 -f "run_benchmark" 2>/dev/null || true
pkill -9 -f "bench_server" 2>/dev/null || true
pkill -9 -f "tsx.*run_benchmark" 2>/dev/null || true
lsof -ti:8765 | xargs kill -9 2>/dev/null || true
sleep 2
echo "✓ Cleaned up old processes"
echo ""

# 2. 加载环境变量
echo "=== Environment ==="
cd /Users/a86135/Desktop/A2S/A2S
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    exit 1
fi
export $(cat .env | grep -v '^#' | xargs)
echo "✓ Environment loaded"
echo ""

# 3. 编译 TypeScript
echo "=== Build ==="
cd agenttree
npm run build > /dev/null 2>&1
echo "✓ TypeScript compiled"
echo ""

# 4. 运行 Benchmark
echo "=== Running Benchmark ==="
npx tsx examples/run_benchmark.ts \
    --benchmark stulife \
    --episodes $EPISODES \
    --max-steps $MAX_STEPS

# 5. 验证结果
echo ""
echo "=== Results ==="
LATEST=$(ls -td ../results/stulife/stulife_* 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "❌ No results found"
    exit 1
fi

echo "Results directory: $LATEST"
echo ""

# 检查文件
for file in tier1_runs.json tier2_worker_actions.json tier3_api_calls.json; do
    if [ -f "$LATEST/$file" ]; then
        SIZE=$(du -h "$LATEST/$file" | cut -f1)
        COUNT=$(cat "$LATEST/$file" | jq '. | length' 2>/dev/null || echo "0")
        echo "✓ $file: $COUNT entries ($SIZE)"
    else
        echo "❌ $file: missing"
    fi
done

echo ""
echo "=========================================="
echo "  Benchmark Complete!"
echo "=========================================="
