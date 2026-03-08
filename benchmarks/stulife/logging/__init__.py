"""
Three-tier logging system for StuLife benchmark

Tier 1: Benchmark layer - StuLife native runs.json format
Tier 2: Abstract layer - Worker manager behavior decisions
Tier 3: Detailed layer - Complete API call context windows
"""

from .coordinator import LoggingCoordinator
from .context import LoggingContext, get_logging_context, set_logging_context

__all__ = [
    "LoggingCoordinator",
    "LoggingContext",
    "get_logging_context",
    "set_logging_context",
]
