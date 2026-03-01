"""
Benchmark Description Reader for Auto-Expansion Agent Cluster

This module reads and parses benchmark introduction files to extract
structured metadata that agents can use to understand task types and
generate appropriate agent trees.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import yaml

from pydantic import BaseModel, Field


class TaskType(BaseModel):
    """Represents a type of task within a benchmark"""
    name: str = Field(description="Name of the task type")
    complexity: str = Field(description="Complexity level: low, medium, high")
    tools: List[str] = Field(description="List of tool names required for this task")
    description: Optional[str] = Field(default=None, description="Optional description")


class SkillCategory(BaseModel):
    """Represents a category of skills"""
    category: str = Field(description="Category name (e.g., navigation, email)")
    skills: List[str] = Field(description="List of skill/tool names in this category")


class SuggestedArchitecture(BaseModel):
    """Suggested initial agent architecture for the benchmark"""
    initial_workers: int = Field(description="Number of initial worker agents")
    initial_managers: int = Field(description="Number of initial manager agents")
    expansion_strategy: str = Field(description="Strategy for expansion: performance_driven, task_driven, hybrid")


class EnvironmentConfig(BaseModel):
    """Environment configuration for the benchmark"""
    wrapper: str = Field(description="Python class path for environment wrapper")
    config_file: Optional[str] = Field(default=None, description="Optional config file path")


class BenchmarkIntro(BaseModel):
    """
    Benchmark introduction metadata

    This contains structured information about a benchmark that agents
    can read to understand task types and generate appropriate agent trees.
    """
    benchmark: Dict[str, Any] = Field(description="Basic benchmark info (name, version, domain)")
    description: str = Field(description="Benchmark description")
    task_types: List[TaskType] = Field(description="List of task types in this benchmark")
    initial_skills: List[SkillCategory] = Field(description="Initial skill categories")
    suggested_architecture: SuggestedArchitecture = Field(description="Suggested agent architecture")
    environment: EnvironmentConfig = Field(description="Environment configuration")

    class Config:
        arbitrary_types_allowed = True


class BenchmarkDescriptionReader:
    """
    Reads benchmark introduction files and parses them into structured metadata

    Usage:
        reader = BenchmarkDescriptionReader()
        intro = reader.read_benchmark_intro("stulife")
        print(intro.benchmark["name"])
        for task_type in intro.task_types:
            print(f"{task_type.name}: {task_type.complexity}")
    """

    def __init__(self, benchmarks_dir: Optional[str] = None):
        """
        Initialize the reader

        Args:
            benchmarks_dir: Path to benchmarks directory. If None, uses default.
        """
        if benchmarks_dir is None:
            # Default to benchmarks/ directory relative to project root
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            benchmarks_dir = project_root / "benchmarks"

        self.benchmarks_dir = Path(benchmarks_dir)

    def read_benchmark_intro(self, benchmark_name: str) -> BenchmarkIntro:
        """
        Read benchmark introduction for a specific benchmark

        Args:
            benchmark_name: Name of the benchmark (e.g., "stulife", "alfworld")

        Returns:
            BenchmarkIntro object with parsed metadata

        Raises:
            FileNotFoundError: If benchmark intro file doesn't exist
            ValueError: If intro file is invalid or fails validation
        """
        intro_path = self._get_intro_path(benchmark_name)

        if not intro_path.exists():
            raise FileNotFoundError(
                f"Benchmark intro not found: {intro_path}\n"
                f"Available benchmarks: {self._list_available_benchmarks()}"
            )

        # Load YAML file
        with open(intro_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Validate and parse with Pydantic
        try:
            return BenchmarkIntro(**data)
        except Exception as e:
            raise ValueError(f"Invalid benchmark intro format: {e}")

    def _get_intro_path(self, benchmark_name: str) -> Path:
        """Get path to benchmark intro file"""
        return self.benchmarks_dir / benchmark_name / "benchmark_intro.yaml"

    def _list_available_benchmarks(self) -> List[str]:
        """List all available benchmarks with intro files"""
        available = []
        for benchmark_dir in self.benchmarks_dir.iterdir():
            if benchmark_dir.is_dir():
                intro_file = benchmark_dir / "benchmark_intro.yaml"
                if intro_file.exists():
                    available.append(benchmark_dir.name)
        return available

    def list_task_types(self, benchmark_name: str) -> List[str]:
        """
        Get list of task types for a benchmark

        Args:
            benchmark_name: Name of the benchmark

        Returns:
            List of task type names
        """
        intro = self.read_benchmark_intro(benchmark_name)
        return [task.name for task in intro.task_types]

    def get_tools_for_task_type(
        self,
        benchmark_name: str,
        task_type: str
    ) -> List[str]:
        """
        Get tools required for a specific task type

        Args:
            benchmark_name: Name of the benchmark
            task_type: Name of the task type

        Returns:
            List of tool names
        """
        intro = self.read_benchmark_intro(benchmark_name)
        for task in intro.task_types:
            if task.name == task_type:
                return task.tools
        raise ValueError(f"Task type '{task_type}' not found in benchmark '{benchmark_name}'")

    def get_skill_categories(self, benchmark_name: str) -> Dict[str, List[str]]:
        """
        Get skill categories for a benchmark

        Args:
            benchmark_name: Name of the benchmark

        Returns:
            Dict mapping category names to lists of skills
        """
        intro = self.read_benchmark_intro(benchmark_name)
        return {
            category.category: category.skills
            for category in intro.initial_skills
        }

    def get_suggested_architecture(self, benchmark_name: str) -> SuggestedArchitecture:
        """
        Get suggested agent architecture for a benchmark

        Args:
            benchmark_name: Name of the benchmark

        Returns:
            SuggestedArchitecture object
        """
        intro = self.read_benchmark_intro(benchmark_name)
        return intro.suggested_architecture


# Convenience functions
def read_benchmark_intro(benchmark_name: str) -> BenchmarkIntro:
    """Convenience function to read benchmark intro"""
    reader = BenchmarkDescriptionReader()
    return reader.read_benchmark_intro(benchmark_name)


def list_available_benchmarks() -> List[str]:
    """Convenience function to list available benchmarks"""
    reader = BenchmarkDescriptionReader()
    return reader._list_available_benchmarks()
