"""
Prompt Initializer for Auto-Expansion Agent Cluster

This module initializes the entire prompt caching system before running tasks.
It analyzes benchmarks and generates cache-optimized prompts for all agents.

Workflow:
1. Benchmark Analysis → Understand domains, tools, patterns
2. Static Prefix Generation → Create ~1200 token prompts for each domain
3. Cache Initialization → Store prompts in PromptCacheManager
4. Agent Tree Prompt Assignment → Assign prompts to agents

Usage:
    initializer = PromptInitializer()
    await initializer.initialize_for_benchmark("alfworld")
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

from .benchmark_analyzer import BenchmarkAnalyzer, BenchmarkAnalysis
from .cache_manager import PromptCacheManager, CacheTier
from .prompt_optimizer import PromptOptimizer

logger = logging.getLogger(__name__)


class PromptInitializer:
    """
    Initialize prompt caching system for a benchmark

    This orchestrates:
    1. Deep benchmark analysis
    2. LLM-driven prompt generation
    3. Cache population with optimized prompts
    4. Validation and reporting
    """

    def __init__(
        self,
        use_llm: bool = True,
        llm_client=None,
        cache_manager: Optional[PromptCacheManager] = None
    ):
        """
        Initialize prompt system

        Args:
            use_llm: Whether to use LLM for prompt generation
            llm_client: LLM client (optional, will create if needed)
            cache_manager: Prompt cache manager (optional, will use singleton)
        """
        self.use_llm = use_llm
        self.llm_client = llm_client
        self.cache_manager = cache_manager

        # Initialize components
        self.benchmark_analyzer = BenchmarkAnalyzer(
            use_llm=use_llm,
            llm_client=llm_client
        )

        if self.cache_manager is None:
            from .cache_manager import get_prompt_cache_manager
            self.cache_manager = get_prompt_cache_manager()

        self.prompt_optimizer = PromptOptimizer(llm_client=llm_client)

        logger.info("PromptInitializer initialized")

    async def initialize_for_benchmark(
        self,
        benchmark_name: str,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Initialize prompt caching system for a benchmark

        This is the main entry point. Call this before running any tasks.

        Args:
            benchmark_name: Name of benchmark (e.g., "alfworld", "stulife")
            force_regenerate: Force regeneration even if prompts exist

        Returns:
            Initialization report with statistics
        """
        logger.info(f"Initializing prompt system for benchmark: {benchmark_name}")

        # Step 1: Analyze benchmark
        logger.info("Step 1: Analyzing benchmark...")
        analysis = self.benchmark_analyzer.analyze_benchmark(benchmark_name)

        # Step 2: Check if prompts already exist
        if not force_regenerate:
            existing = self._check_existing_prompts(analysis)
            if existing:
                logger.info(f"Using {len(existing)} existing prompts")
                return {
                    "status": "using_existing",
                    "benchmark": benchmark_name,
                    "domains_loaded": list(existing.keys()),
                    "analysis": analysis
                }

        # Step 3: Generate static prefixes
        logger.info("Step 2: Generating static prefixes...")
        static_prefixes = self.benchmark_analyzer.generate_static_prefixes(
            analysis,
            use_llm_generation=self.use_llm
        )

        # Step 4: Populate cache
        logger.info("Step 3: Populating prompt cache...")
        cache_results = self._populate_cache(analysis, static_prefixes)

        # Step 5: Validate prompts
        logger.info("Step 4: Validating prompts...")
        validation_results = self._validate_prompts(analysis, static_prefixes)

        # Step 6: Generate report
        report = self._generate_initialization_report(
            benchmark_name,
            analysis,
            cache_results,
            validation_results
        )

        logger.info(f"Initialization complete: {report['total_prompts_generated']} prompts")
        return report

    def initialize_for_agent_tree(
        self,
        agent_tree,
        benchmark_name: str
    ) -> Dict[str, Any]:
        """
        Initialize prompts for an existing agent tree

        Use this if you already have an agent tree and need to add prompts.

        Args:
            agent_tree: Existing agent tree
            benchmark_name: Name of benchmark

        Returns:
            Initialization report
        """
        logger.info(f"Initializing prompts for agent tree ({len(agent_tree.workers)} workers)")

        # Analyze benchmark to get domain info
        analysis = self.benchmark_analyzer.analyze_benchmark(benchmark_name)

        # Generate prompts for all domains in the tree
        static_prefixes = self.benchmark_analyzer.generate_static_prefixes(
            analysis,
            use_llm_generation=self.use_llm
        )

        # Populate cache
        cache_results = self._populate_cache(analysis, static_prefixes)

        return {
            "status": "success",
            "benchmark": benchmark_name,
            "domains_initialized": list(static_prefixes.keys()),
            "cache_results": cache_results
        }

    def update_prompts_after_extension(
        self,
        old_tree,
        new_tree,
        performance_data: List[Any]
    ) -> Dict[str, Any]:
        """
        Update prompts after agent tree extension

        This is called automatically when the agent tree is extended.

        Args:
            old_tree: Agent tree before extension
            new_tree: Agent tree after extension
            performance_data: Performance history for optimization

        Returns:
            Update report
        """
        logger.info("Updating prompts after agent tree extension")

        # Find new domains/agents
        old_domains = set(w.metadata.get("prompt_builder_domain", w.domain) for w in old_tree.workers)
        new_domains = set(w.metadata.get("prompt_builder_domain", w.domain) for w in new_tree.workers)

        added_domains = new_domains - old_domains

        if not added_domains:
            logger.info("No new domains, optimizing existing prompts")
            # Optimize existing prompts based on performance
            optimization_results = self.prompt_optimizer.optimize_after_extension(
                new_tree.workers,
                performance_data
            )

            return {
                "status": "optimized",
                "new_domains": [],
                "optimized_domains": [r.domain for r in optimization_results],
                "results": optimization_results
            }

        logger.info(f"New domains detected: {added_domains}")

        # Generate prompts for new domains
        benchmark_name = new_tree.metadata.get("benchmark", "unknown")
        analysis = self.benchmark_analyzer.analyze_benchmark(benchmark_name)

        # Filter to only new domains
        new_domains_analysis = BenchmarkAnalysis(
            benchmark_name=benchmark_name,
            domains={d: analysis.domains[d] for d in added_domains if d in analysis.domains},
            task_types=analysis.task_types,
            tools_catalog={d: analysis.tools_catalog[d] for d in added_domains if d in analysis.tools_catalog},
            coordination_requirements=analysis.coordination_requirements,
            performance_expectations=analysis.performance_expectations,
            metadata=analysis.metadata
        )

        static_prefixes = self.benchmark_analyzer.generate_static_prefixes(
            new_domains_analysis,
            use_llm_generation=self.use_llm
        )

        cache_results = self._populate_cache(new_domains_analysis, static_prefixes)

        return {
            "status": "extended",
            "new_domains": list(added_domains),
            "prompts_added": list(static_prefixes.keys()),
            "cache_results": cache_results
        }

    # ========== Private Methods ==========

    def _check_existing_prompts(
        self,
        analysis: BenchmarkAnalysis
    ) -> Optional[Dict[str, str]]:
        """Check if prompts already exist for all domains"""
        existing = {}
        for domain_name in analysis.domains.keys():
            cached = self.cache_manager.get_cached_prompt(
                domain_name, "worker", CacheTier.STATIC_PREFIX
            )
            if cached:
                existing[domain_name] = cached.content

        return existing if len(existing) == len(analysis.domains) else None

    def _populate_cache(
        self,
        analysis: BenchmarkAnalysis,
        static_prefixes: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Populate cache with generated prompts"""
        results = []

        for domain_name, prompt_content in static_prefixes.items():
            # Update cache for each domain
            result = self.cache_manager.update_cached_prompt(
                domain=domain_name,
                role="worker",
                tier=CacheTier.STATIC_PREFIX,
                content=prompt_content,
                update_reason="initial_generation",
                metadata={
                    "benchmark": analysis.benchmark_name,
                    "generated_by": "benchmark_analyzer",
                    "tool_count": len(analysis.domains[domain_name].tools)
                }
            )
            results.append({
                "domain": domain_name,
                "version": result.new_version,
                "cache_hit_after": result.cache_hit_after
            })

        return results

    def _validate_prompts(
        self,
        analysis: BenchmarkAnalysis,
        static_prefixes: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate generated prompts"""
        validation_results = {}

        for domain_name, prompt_content in static_prefixes.items():
            # Check prompt length
            estimated_tokens = len(prompt_content) // 4
            domain_analysis = analysis.domains[domain_name]

            validation_results[domain_name] = {
                "estimated_tokens": estimated_tokens,
                "target_tokens": domain_analysis.estimated_prompt_length,
                "length_ok": 800 <= estimated_tokens <= 1500,
                "has_required_sections": all(
                    section in prompt_content
                    for section in [
                        "<role_definition>",
                        "<core_protocol>",
                        "<tool_specifications>",
                        "<error_prevention>"
                    ]
                ),
                "cache_hit_potential": self._estimate_cache_potential(prompt_content)
            }

        return validation_results

    def _estimate_cache_potential(self, prompt: str) -> str:
        """Estimate cache hit potential"""
        # Count lines in static sections
        static_sections = [
            "role_definition", "core_protocol", "workflow_structure",
            "tool_specifications", "error_prevention"
        ]

        lines = prompt.split('\n')
        static_lines = sum(
            1 for line in lines
            if any(section in line for section in static_sections)
        )

        ratio = static_lines / len(lines) if lines else 0

        if ratio >= 0.7:
            return "high"
        elif ratio >= 0.5:
            return "medium"
        else:
            return "low"

    def _generate_initialization_report(
        self,
        benchmark_name: str,
        analysis: BenchmarkAnalysis,
        cache_results: List[Dict[str, Any]],
        validation_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate initialization report"""
        total_tokens = sum(
            v["estimated_tokens"] for v in validation_results.values()
        )

        return {
            "status": "success",
            "benchmark": benchmark_name,
            "total_prompts_generated": len(cache_results),
            "total_domains": len(analysis.domains),
            "total_tools": sum(len(d.tools) for d in analysis.domains.values()),
            "total_estimated_tokens": total_tokens,
            "average_tokens_per_prompt": total_tokens // len(cache_results) if cache_results else 0,
            "cache_results": cache_results,
            "validation": validation_results,
            "cache_performance": self.cache_manager.analyze_cache_performance()
        }


# Convenience function for quick initialization
async def initialize_prompts_for_benchmark(
    benchmark_name: str,
    use_llm: bool = True,
    llm_client=None,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    Initialize prompts for a benchmark (convenience function)

    Usage:
        from core.prompts.initializer import initialize_prompts_for_benchmark

        report = await initialize_prompts_for_benchmark("alfworld")
        print(f"Initialized {report['total_prompts_generated']} prompts")
    """
    initializer = PromptInitializer(
        use_llm=use_llm,
        llm_client=llm_client
    )

    return await initializer.initialize_for_benchmark(
        benchmark_name,
        force_regenerate=force_regenerate
    )
