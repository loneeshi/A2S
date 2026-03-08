"""
Validation script to demonstrate expected output formats

Shows example output for each tier of the logging system.
"""

import json
from pathlib import Path

print("=" * 80)
print("THREE-TIER LOGGING SYSTEM - EXPECTED OUTPUT FORMATS")
print("=" * 80)

# Tier 1: runs.json format
print("\n📊 TIER 1: Benchmark Layer (runs.json)")
print("-" * 80)
tier1_example = [
    {
        "task_name": "campus_life_bench",
        "sample_index": "task_001",
        "sample_status": "CORRECT",
        "chat_history": [
            {"role": "USER", "content": "Where is the library?"},
            {"role": "AGENT", "content": "The library is in Building A."},
        ],
        "evaluation_record": {
            "outcome": "CORRECT",
            "detail_dict": {"score": 1.0, "reason": "Correct answer provided"},
        },
    }
]
print(json.dumps(tier1_example, indent=2))
print(f"\n📁 Output: benchmarks/stulife_source/Stulife/result/{{model_name}}/runs.json")
print("✅ Compatible with calculate_stulife_metrics.py")

# Tier 2: worker_actions.json format
print("\n\n🎯 TIER 2: Abstract Layer (worker_actions.json)")
print("-" * 80)
tier2_example = {
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
            "duration_ms": 1234.5,
        },
        {
            "timestamp": "2026-03-08T10:00:02.456",
            "episode_id": "ep-000",
            "step": 2,
            "worker_id": "stulife_worker",
            "task_summary": "Find study room",
            "action_taken": "check available rooms",
            "decision_rationale": "Need quiet space for studying",
            "tools_used": [],
            "duration_ms": 987.3,
        },
    ],
}
print(json.dumps(tier2_example, indent=2))
print(f"\n📁 Output: results/stulife/{{run_id}}_worker_actions.json")
print("✅ Quick scanning of worker behavior")

# Tier 3: api_calls.json format
print("\n\n🔍 TIER 3: Detailed Layer (api_calls.json)")
print("-" * 80)
tier3_example = {
    "run_id": "stulife_2026-03-08T10-00-00-000000",
    "api_calls": [
        {
            "call_id": "call-0001",
            "timestamp": "2026-03-08T10:00:01.123",
            "episode_id": "ep-000",
            "step": 1,
            "worker_id": "stulife_worker",
            "request": {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": "You are a student assistant. Task: Navigate to library. Current situation: You are at the campus entrance.",
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            },
            "response": {
                "content": "I'll go to the library. It's located in Building A, which is straight ahead from the entrance.",
                "finish_reason": "stop",
            },
            "usage": {
                "prompt_tokens": 1234,
                "completion_tokens": 567,
                "total_tokens": 1801,
            },
            "cache_info": {"cache_read_input_tokens": 1200},
            "latency_ms": 1234.5,
            "error": None,
        }
    ],
}
print(json.dumps(tier3_example, indent=2)[:1000] + "...")
print(f"\n📁 Output: results/stulife/{{run_id}}_api_calls.json")
print("✅ Complete context window for debugging")

# Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
The three-tier logging system captures:

1. Tier 1 (Benchmark): Native StuLife format for metric calculation
   - Session objects with chat history
   - Evaluation records with outcomes
   - Compatible with existing tools

2. Tier 2 (Abstract): High-level worker behavior
   - Task summaries and actions taken
   - Decision rationales
   - Execution durations
   - Easy to scan and analyze

3. Tier 3 (Detailed): Complete API call context
   - Full request/response data
   - Token usage and cache information
   - Latency measurements
   - Error tracking

All three tiers are automatically generated when running the StuLife benchmark.
""")
print("=" * 80)
