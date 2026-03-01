"""
Generator Module for Auto-Expansion Agent Cluster

This module handles the generation and initialization of agent trees
based on benchmark descriptions and environment exploration.
"""

from .description_reader import (
    BenchmarkDescriptionReader,
    BenchmarkIntro,
    TaskType,
    SkillCategory,
    SuggestedArchitecture,
    EnvironmentConfig,
    read_benchmark_intro,
    list_available_benchmarks,
)

from .tree_builder import (
    AgentTreeGenerator,
    AgentDefinition,
    AgentTree,
    generate_tree,
)

from .env_explorer import (
    EnvironmentExplorer,
    ExplorationResult,
    EpisodeResult,
    GapAnalysis,
)

__all__ = [
    "BenchmarkDescriptionReader",
    "BenchmarkIntro",
    "TaskType",
    "SkillCategory",
    "SuggestedArchitecture",
    "EnvironmentConfig",
    "read_benchmark_intro",
    "list_available_benchmarks",
    "AgentTreeGenerator",
    "AgentDefinition",
    "AgentTree",
    "generate_tree",
    "EnvironmentExplorer",
    "ExplorationResult",
    "EpisodeResult",
    "GapAnalysis",
]
