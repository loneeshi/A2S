#!/bin/bash

# 验证 StuLife Benchmark 结果

if [ -z "$1" ]; then
    # 如果没有提供参数，使用最新的结果目录
    RESULT_DIR=$(ls -td /Users/a86135/Desktop/A2S/A2S/results/stulife/stulife_* 2>/dev/null | head -1)
else
    RESULT_DIR="$1"
fi

if [ ! -d "$RESULT_DIR" ]; then
    echo "❌ Result directory not found: $RESULT_DIR"
    exit 1
fi

echo "========================================"
echo "  StuLife Benchmark Result Validation"
echo "========================================"
echo ""
echo "Directory: $RESULT_DIR"
echo ""

# 检查文件是否存在
echo "=== File Check ==="
for file in tier1_runs.json tier2_worker_actions.json tier3_api_calls.json; do
    if [ -f "$RESULT_DIR/$file" ]; then
        SIZE=$(du -h "$RESULT_DIR/$file" | cut -f1)
        echo "✓ $file ($SIZE)"
    else
        echo "❌ $file (missing)"
    fi
done
echo ""

# 检查 tier1_runs.json
echo "=== Tier 1: Session Data ==="
if [ -f "$RESULT_DIR/tier1_runs.json" ]; then
    SESSION_COUNT=$(cat "$RESULT_DIR/tier1_runs.json" | jq '. | length' 2>/dev/null || echo "0")
    echo "Sessions: $SESSION_COUNT"

    if [ "$SESSION_COUNT" -gt "0" ]; then
        echo ""
        echo "Sample statuses:"
        cat "$RESULT_DIR/tier1_runs.json" | jq -r '.[] | "\(.sample_index): \(.sample_status)"' 2>/dev/null | head -10

        echo ""
        echo "First session keys:"
        cat "$RESULT_DIR/tier1_runs.json" | jq '.[0] | keys' 2>/dev/null | head -15
    else
        echo "⚠️  No sessions found!"
    fi
else
    echo "❌ tier1_runs.json not found"
fi
echo ""

# 检查 tier2_worker_actions.json
echo "=== Tier 2: Worker Actions ==="
if [ -f "$RESULT_DIR/tier2_worker_actions.json" ]; then
    ACTION_COUNT=$(cat "$RESULT_DIR/tier2_worker_actions.json" | jq '. | length' 2>/dev/null || echo "0")
    echo "Actions: $ACTION_COUNT"

    if [ "$ACTION_COUNT" -gt "0" ]; then
        echo ""
        echo "Sample actions:"
        cat "$RESULT_DIR/tier2_worker_actions.json" | jq -r '.[0:3] | .[] | "\(.timestamp): \(.action_taken[0:60])"' 2>/dev/null
    fi
else
    echo "❌ tier2_worker_actions.json not found"
fi
echo ""

# 检查 tier3_api_calls.json
echo "=== Tier 3: API Calls ==="
if [ -f "$RESULT_DIR/tier3_api_calls.json" ]; then
    API_COUNT=$(cat "$RESULT_DIR/tier3_api_calls.json" | jq '. | length' 2>/dev/null || echo "0")
    echo "API Calls: $API_COUNT"

    if [ "$API_COUNT" -gt "0" ]; then
        TOTAL_TOKENS=$(cat "$RESULT_DIR/tier3_api_calls.json" | jq '[.[] | .usage.total_tokens // 0] | add' 2>/dev/null || echo "0")
        echo "Total Tokens: $TOTAL_TOKENS"

        AVG_LATENCY=$(cat "$RESULT_DIR/tier3_api_calls.json" | jq '[.[] | .latency_ms // 0] | add / length | round' 2>/dev/null || echo "0")
        echo "Avg Latency: ${AVG_LATENCY}ms"
    fi
else
    echo "❌ tier3_api_calls.json not found"
fi
echo ""

# 总结
echo "========================================"
echo "  Validation Summary"
echo "========================================"

PASS=true

if [ ! -f "$RESULT_DIR/tier1_runs.json" ]; then
    echo "❌ tier1_runs.json missing"
    PASS=false
elif [ "$SESSION_COUNT" -eq "0" ]; then
    echo "❌ No sessions saved"
    PASS=false
else
    echo "✓ tier1_runs.json: $SESSION_COUNT sessions"
fi

if [ ! -f "$RESULT_DIR/tier2_worker_actions.json" ]; then
    echo "❌ tier2_worker_actions.json missing"
    PASS=false
else
    echo "✓ tier2_worker_actions.json: $ACTION_COUNT actions"
fi

if [ ! -f "$RESULT_DIR/tier3_api_calls.json" ]; then
    echo "❌ tier3_api_calls.json missing"
    PASS=false
else
    echo "✓ tier3_api_calls.json: $API_COUNT calls"
fi

echo ""
if [ "$PASS" = true ]; then
    echo "✅ All checks passed!"
    exit 0
else
    echo "❌ Some checks failed"
    exit 1
fi
