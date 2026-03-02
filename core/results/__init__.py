"""
Results Module for Auto-Expansion Agent Cluster

This module handles recording and managing test results.
"""

from .results import (
    ResultsRecorder,
    EpisodeResult,
    BenchmarkResults,
)

__all__ = [
    "ResultsRecorder",
    "EpisodeResult",
    "BenchmarkResults",
]
