"""
Agent Tree Generator for Auto-Expansion Agent Cluster

This module generates initial agent trees based on benchmark descriptions.
It implements the hybrid initialization approach:
- Phase 1: Read benchmark description → generate initial tree
- Phase 2: Environment exploration → refine tree (handled by env_explorer.py)
"""

from typing import Dict, List, Any, Optional
import logging
from pydantic import BaseModel

from .description_reader import BenchmarkDescriptionReader, BenchmarkIntro
from ..prompts.prompt_builder import CacheOptimizedPromptBuilder


logger = logging.getLogger(__name__)


class AgentDefinition(BaseModel):
    """Definition of an agent in the tree"""
    name: str
    role: str  # "worker" | "manager"
    domain: Optional[str] = None  # e.g., "navigation", "email"
    tools: List[str] = []
    prompt: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AgentTree(BaseModel):
    """
    Represents an agent tree structure

    A tree consists of:
    - workers: Leaf nodes that perform specific tasks
    - managers: Internal nodes that coordinate workers
    """
    workers: List[AgentDefinition] = []
    managers: List[AgentDefinition] = []
    metadata: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class AgentTreeGenerator:
    """
    Generate agent trees from benchmark descriptions

    This implements Phase 1 of hybrid initialization:
    1. Read benchmark intro
    2. Extract tool categories
    3. Create workers for each category
    4. Create managers for coordination
    5. Build prompts using cache-optimized builder
    """

    def __init__(
        self,
        description_reader: Optional[BenchmarkDescriptionReader] = None
    ):
        """
        Initialize the tree generator

        Args:
            description_reader: Reader for benchmark intros. If None, creates default.
        """
        self.description_reader = description_reader or BenchmarkDescriptionReader()

    def generate_initial_tree(self, benchmark_name: str) -> AgentTree:
        """
        Generate initial agent tree from benchmark description

        Args:
            benchmark_name: Name of the benchmark (e.g., "stulife")

        Returns:
            AgentTree with workers and managers
        """
        logger.info(f"Generating initial tree for benchmark: {benchmark_name}")

        # Step 1: Read benchmark intro
        intro = self.description_reader.read_benchmark_intro(benchmark_name)

        # Step 2: Extract tool categories from initial_skills
        skill_categories = self.description_reader.get_skill_categories(benchmark_name)

        # Step 3: Create workers for each skill category
        workers = self._create_workers(skill_categories, intro)

        # Step 4: Create managers based on suggested architecture
        managers = self._create_managers(intro)

        # Step 5: Build tree
        tree = AgentTree(
            workers=workers,
            managers=managers,
            metadata={
                "benchmark": benchmark_name,
                "domain": intro.benchmark.get("domain"),
                "version": intro.benchmark.get("version"),
                "initialization_phase": "description_based",
            }
        )

        logger.info(
            f"Generated tree with {len(workers)} workers and {len(managers)} managers"
        )

        return tree

    def _create_workers(
        self,
        skill_categories: Dict[str, List[str]],
        intro: BenchmarkIntro
    ) -> List[AgentDefinition]:
        """
        Create worker agents for each skill category

        Args:
            skill_categories: Dict mapping category names to tool lists
            intro: Benchmark introduction

        Returns:
            List of AgentDefinition workers
        """
        workers = []

        for category, tools in skill_categories.items():
            # Create prompt builder for this domain
            # Map category to domain name
            domain = self._map_category_to_domain(category)

            try:
                prompt_builder = CacheOptimizedPromptBuilder(domain)

                # Build worker prompt
                prompt = prompt_builder.build_prompt(
                    role="worker",
                    task_context={"category": category},
                    include_examples=False  # No dynamic examples initially
                )

                # Create worker agent
                worker = AgentDefinition(
                    name=f"{category.capitalize()}Worker",
                    role="worker",
                    domain=domain,
                    tools=tools,
                    prompt=prompt,
                    metadata={
                        "category": category,
                        "num_tools": len(tools),
                        "prompt_builder_domain": domain,
                    }
                )

                workers.append(worker)

            except Exception as e:
                logger.warning(f"Failed to create worker for category {category}: {e}")
                # Create worker with minimal prompt
                worker = AgentDefinition(
                    name=f"{category.capitalize()}Worker",
                    role="worker",
                    domain=category,
                    tools=tools,
                    prompt=None,  # Will be created later
                    metadata={
                        "category": category,
                        "num_tools": len(tools),
                        "prompt_error": str(e),
                    }
                )
                workers.append(worker)

        return workers

    def _create_managers(self, intro: BenchmarkIntro) -> List[AgentDefinition]:
        """
        Create manager agents based on suggested architecture

        Args:
            intro: Benchmark introduction

        Returns:
            List of AgentDefinition managers
        """
        managers = []
        architecture = intro.suggested_architecture

        # Create task coordinator manager
        coordinator = AgentDefinition(
            name="TaskCoordinator",
            role="manager",
            domain="general",
            tools=[],  # Managers coordinate, don't use tools directly
            prompt=None,  # Will be created with manager-specific structure
            metadata={
                "type": "coordinator",
                "responsibility": "Route tasks to appropriate workers",
            }
        )
        managers.append(coordinator)

        # Create performance monitor manager
        if architecture.initial_managers > 1:
            monitor = AgentDefinition(
                name="PerformanceMonitor",
                role="manager",
                domain="general",
                tools=[],
                prompt=None,
                metadata={
                    "type": "monitor",
                    "responsibility": "Monitor performance and trigger expansions",
                }
            )
            managers.append(monitor)

        return managers

    def _map_category_to_domain(self, category: str) -> str:
        """
        Map skill category to prompt builder domain

        Args:
            category: Skill category name

        Returns:
            Domain name for prompt builder
        """
        # Direct mapping for common categories
        category_to_domain = {
            "navigation": "navigation",
            "email": "email",
            "course": "course",
            "calendar": "course",  # Reuse course domain for calendar
            "reservation": "course",  # Reuse course domain
        }

        return category_to_domain.get(category.lower(), category.lower())

    def refine_tree_with_exploration(
        self,
        tree: AgentTree,
        exploration_results: Dict[str, Any]
    ) -> AgentTree:
        """
        Refine agent tree based on environment exploration results

        This is a placeholder for Phase 2 refinement.
        Actual implementation will be in env_explorer.py

        Args:
            tree: Initial agent tree
            exploration_results: Results from environment exploration

        Returns:
            Refined agent tree
        """
        # Placeholder: apply refinements based on exploration
        # This will be implemented by the EnvironmentExplorer

        logger.info("Refining tree with exploration results (placeholder)")

        # Update metadata
        tree.metadata["initialization_phase"] = "exploration_refined"
        tree.metadata["exploration_results"] = exploration_results

        return tree


# Convenience functions
def generate_tree(benchmark_name: str) -> AgentTree:
    """Convenience function to generate agent tree"""
    generator = AgentTreeGenerator()
    return generator.generate_initial_tree(benchmark_name)
