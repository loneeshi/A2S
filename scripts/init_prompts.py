#!/usr/bin/env python3
"""
Initialize Prompt Caching System for Auto-Expansion Agent Cluster

This script analyzes benchmarks and generates cache-optimized prompts
before running any tasks.

Usage:
    python scripts/init_prompts.py --benchmark alfworld
    python scripts/init_prompts.py --benchmark stulife --use-llm
    python scripts/init_prompts.py --benchmark alfworld --force-regenerate
"""

import sys
import logging
import argparse
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.prompts import PromptInitializer, initialize_prompts_for_benchmark
from core.llm import LLMClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


async def initialize_benchmark_prompts(
    benchmark_name: str,
    use_llm: bool = False,
    force_regenerate: bool = False
):
    """Initialize prompts for a benchmark"""

    print_section(f"Initializing Prompts for {benchmark_name.upper()}")

    # Initialize LLM client if requested
    llm_client = None
    if use_llm:
        logger.info("Initializing LLM client for prompt generation...")
        try:
            llm_client = LLMClient(default_model="gemini-2.5-flash")
            logger.info("✅ LLM client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize LLM client: {e}")
            logger.info("Falling back to template-based generation...")
            use_llm = False

    # Initialize prompts
    initializer = PromptInitializer(use_llm=use_llm, llm_client=llm_client)

    print(f"Mode: {'LLM-based generation' if use_llm else 'Template-based generation'}")
    print(f"Force regenerate: {force_regenerate}")
    print()

    try:
        report = await initializer.initialize_for_benchmark(
            benchmark_name,
            force_regenerate=force_regenerate
        )

        print_section("Initialization Results")

        if report["status"] == "using_existing":
            print(f"✅ Using existing prompts for {benchmark_name}")
            print(f"\nDomains loaded: {', '.join(report['domains_loaded'])}")

            # Show performance
            cache_perf = report["analysis"].domains
            for domain, analysis in cache_perf.items():
                print(f"\n  {domain}:")
                print(f"    Tools: {len(analysis.tools)}")
                print(f"    Task types: {len(analysis.task_types)}")
                print(f"    Complexity: {analysis.complexity}")

        else:
            print(f"✅ Generated {report['total_prompts_generated']} prompts")
            print(f"\nStatistics:")
            print(f"  Total domains: {report['total_domains']}")
            print(f"  Total tools: {report['total_tools']}")
            print(f"  Total tokens: {report['total_estimated_tokens']}")
            print(f"  Avg tokens per prompt: {report['average_tokens_per_prompt']}")

            # Show validation results
            print(f"\nValidation Results:")
            for domain, validation in report["validation"].items():
                status = "✅" if validation["length_ok"] and validation["cache_hit_potential"] in ["high", "medium"] else "⚠️"
                print(f"\n  {status} {domain}:")
                print(f"    Tokens: {validation['estimated_tokens']} (target: {validation['target_tokens']})")
                print(f"    Required sections: {'✅' if validation['has_required_sections'] else '❌'}")
                print(f"    Cache hit potential: {validation['cache_hit_potential'].upper()}")

            # Show cache performance
            cache_perf = report.get("cache_performance", {})
            if cache_perf:
                print(f"\nCache Performance:")
                print(f"  Total cached prompts: {cache_perf.get('total_cached_prompts', 0)}")
                print(f"  Avg static cache hit: {cache_perf.get('average_static_cache_hit', 0):.1%}")
                print(f"  Cache size: {cache_perf.get('cache_size_mb', 0):.2f} MB")

        print_section("Summary")

        print(f"✅ Prompt initialization complete for {benchmark_name}")
        print(f"\nNext steps:")
        print(f"  1. Run agent tree generation: python scripts/generate_tree.py --benchmark {benchmark_name}")
        print(f"  2. Run tasks: python scripts/run_{benchmark_name}.py")
        print(f"  3. Prompts will be automatically optimized after extension")

        return True

    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def inspect_prompts(benchmark_name: str):
    """Inspect existing prompts for a benchmark"""

    from core.prompts import get_prompt_cache_manager

    print_section(f"Inspecting Prompts: {benchmark_name.upper()}")

    manager = get_prompt_cache_manager()

    # Get all cached prompts for this benchmark
    performance = manager.analyze_cache_performance()

    print(f"Cache Statistics:")
    print(f"  Total cached prompts: {performance['total_cached_prompts']}")
    print(f"  Total usage count: {performance['total_usage_count']}")
    print(f"  Average static cache hit: {performance['average_static_cache_hit']:.1%}")
    print(f"  Cache size: {performance['cache_size_mb']:.2f} MB")

    if performance['recent_updates']:
        print(f"\nRecent Updates:")
        for update in performance['recent_updates']:
            print(f"  {update.domain}/{update.role}:")
            print(f"    v{update.old_version} → v{update.new_version}")
            print(f"    Reason: {update.update_reason}")
            if update.cache_hit_before is not None:
                print(f"    Cache hit: {update.cache_hit_before:.1%} → {update.cache_hit_after:.1%}")
                print(f"    Tokens saved: {update.tokens_saved}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize prompt caching system for auto-expansion agent cluster"
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        required=True,
        choices=["alfworld", "stulife", "webshop"],
        help="Benchmark to initialize prompts for"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM for prompt generation (requires OPENAI_API_KEY)"
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Force regeneration even if prompts exist"
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect existing prompts instead of initializing"
    )

    args = parser.parse_args()

    try:
        if args.inspect:
            success = inspect_prompts(args.benchmark)
        else:
            success = asyncio.run(initialize_benchmark_prompts(
                args.benchmark,
                use_llm=args.use_llm,
                force_regenerate=args.force_regenerate
            ))

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\n\nInitialization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
