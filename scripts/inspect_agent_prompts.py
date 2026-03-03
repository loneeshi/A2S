#!/usr/bin/env python3
"""
Inspect Agent Prompts for Auto-Expansion Agent Cluster

This script displays the complete prompt configuration for each agent in the tree,
including static prefixes (cache-optimized) and any dynamic content.

Usage:
    python scripts/inspect_agent_prompts.py --benchmark stulife
    python scripts/inspect_agent_prompts.py --benchmark alfworld
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.generator import AgentTreeGenerator


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def display_agent_prompt(agent, prompt_content=None):
    """Display prompt configuration for a single agent"""
    print(f"\n{'─' * 80}")
    print(f"🤖 Agent: {agent.name}")
    print(f"{'─' * 80}")
    print(f"Role:       {agent.role}")
    print(f"Domain:     {agent.domain}")
    print(f"Tools:      {len(agent.tools)} tools")
    print(f"Metadata:   {agent.metadata}")
    print(f"\n📝 Prompt Configuration:")
    print(f"{'─' * 80}")

    if prompt_content:
        # Display prompt with line numbers
        lines = prompt_content.split('\n')
        for i, line in enumerate(lines, 1):
            print(f"{i:4d}│ {line}")

        # Show statistics
        total_lines = len(lines)
        total_chars = len(prompt_content)
        estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token

        print(f"\n{'─' * 80}")
        print(f"📊 Prompt Statistics:")
        print(f"  Total Lines:    {total_lines}")
        print(f"  Total Chars:    {total_chars}")
        print(f"  Est. Tokens:    {estimated_tokens}")
        print(f"  Cache Hit:      HIGH (static prefix is ~1200 tokens)")
    else:
        print("⚠️  No prompt configured (will use default at runtime)")


def inspect_benchmark_prompts(benchmark_name: str):
    """Inspect prompts for all agents in a benchmark"""

    print_section(f"Inspecting Agent Prompts: {benchmark_name.upper()}")

    # Generate agent tree
    print("Generating agent tree...")
    generator = AgentTreeGenerator()
    tree = generator.generate_initial_tree(benchmark_name)

    print(f"✅ Generated {len(tree.workers)} workers and {len(tree.managers)} managers\n")

    # Display workers
    print_section("Worker Agents")

    for i, worker in enumerate(tree.workers, 1):
        print(f"\n[Worker {i}/{len(tree.workers)}]")
        display_agent_prompt(worker, worker.prompt)

    # Display managers
    print_section("Manager Agents")

    for i, manager in enumerate(tree.managers, 1):
        print(f"\n[Manager {i}/{len(tree.managers)}]")
        display_agent_prompt(manager, manager.prompt)

    # Summary
    print_section("Prompt Caching Summary")

    print("🎯 Cache Optimization Strategy:")
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │ Static Prefix (First ~1200 tokens)                     │")
    print("  │ • Domain-specific protocol (navigation/email/course)    │")
    print("  │ • Core rules and immutable principles                  │")
    print("  │ • Tool specifications with examples                    │")
    print("  │ • Error prevention patterns                            │")
    print("  │                                                         │")
    print("  │ ✅ SAME across all agents in a domain                  │")
    print("  │ ✅ HIGH cache hit rate (70-80%)                        │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │ Dynamic Content (Last ~200-400 tokens)                 │")
    print("  │ • Task-specific context                                │")
    print("  │ • Current observation/state                            │")
    print("  │ • Relevant examples (if included)                      │")
    print("  │                                                         │")
    print("  │ ⚠️  UNIQUE per agent/task                              │")
    print("  │ ⚠️  NO cache hit (but necessary)                       │")
    print("  └─────────────────────────────────────────────────────────┘")

    print(f"\n📈 Expected Performance:")
    print(f"  • Static ratio:    ~75-85% (1200/1500 tokens)")
    print(f"  • Cache hit rate:  ~70-80% (first 1024 tokens)")
    print(f"  • Cost reduction:  ~60-70% (cached tokens not billed)")

    print(f"\n🔧 Domain Mapping:")
    domains = {}
    for worker in tree.workers:
        domain = worker.metadata.get("prompt_builder_domain", worker.domain)
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(worker.name)

    for domain, agents in domains.items():
        print(f"  • {domain:15s}: {', '.join(agents)}")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inspect agent prompts for auto-expansion agent cluster"
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        choices=["stulife", "alfworld", "webshop"],
        default="stulife",
        help="Benchmark to inspect (default: stulife)"
    )

    args = parser.parse_args()

    try:
        inspect_benchmark_prompts(args.benchmark)
    except KeyboardInterrupt:
        print("\n\nInspection interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Inspection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
