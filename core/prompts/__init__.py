"""
Prompt Caching System for Auto-Expansion Agent Cluster

This module provides comprehensive prompt caching with automatic optimization.

Main Components:
- BenchmarkAnalyzer: Analyze benchmarks to understand domains and patterns
- PromptCacheManager: Manage cached prompts with version tracking
- PromptOptimizer: LLM-driven prompt optimization
- PromptInitializer: Initialize prompt system for benchmarks

Usage:
    from core.prompts import PromptInitializer, initialize_prompts_for_benchmark

    # Initialize prompts for a benchmark
    initializer = PromptInitializer()
    report = await initializer.initialize_for_benchmark("alfworld")

    # Or use convenience function
    report = await initialize_prompts_for_benchmark("alfworld")
"""

from .benchmark_analyzer import (
    BenchmarkAnalyzer,
    BenchmarkAnalysis,
    DomainAnalysis,
)

from .cache_manager import (
    PromptCacheManager,
    CachedPrompt,
    CacheTier,
    PromptUpdateResult,
    get_prompt_cache_manager,
)

from .prompt_optimizer import (
    PromptOptimizer,
    OptimizationSuggestion,
    OptimizationResult,
)

from .initializer import (
    PromptInitializer,
    initialize_prompts_for_benchmark,
)

__all__ = [
    # Benchmark Analysis
    "BenchmarkAnalyzer",
    "BenchmarkAnalysis",
    "DomainAnalysis",

    # Cache Management
    "PromptCacheManager",
    "CachedPrompt",
    "CacheTier",
    "PromptUpdateResult",
    "get_prompt_cache_manager",

    # Prompt Optimization
    "PromptOptimizer",
    "OptimizationSuggestion",
    "OptimizationResult",

    # Initialization
    "PromptInitializer",
    "initialize_prompts_for_benchmark",
]
