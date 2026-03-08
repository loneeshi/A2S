"""
Thread-local context management for logging

Uses contextvars to pass episode_id, worker_id, and other metadata
through the call stack without explicit parameter passing.
"""

from contextvars import ContextVar
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class LoggingContext:
    """Context information for logging"""

    episode_id: Optional[str] = None
    task_id: Optional[str] = None
    step: int = 0
    worker_id: str = "stulife_worker"
    run_id: Optional[str] = None

    # Additional metadata
    metadata: dict = field(default_factory=dict)


# Thread-local context variable
_logging_context: ContextVar[Optional[LoggingContext]] = ContextVar(
    "logging_context", default=None
)


def get_logging_context() -> Optional[LoggingContext]:
    """Get current logging context"""
    return _logging_context.get()


def set_logging_context(context: LoggingContext) -> None:
    """Set logging context"""
    _logging_context.set(context)


def clear_logging_context() -> None:
    """Clear logging context"""
    _logging_context.set(None)


def update_logging_context(**kwargs) -> None:
    """Update specific fields in the current context"""
    ctx = get_logging_context()
    if ctx is None:
        ctx = LoggingContext()
        set_logging_context(ctx)

    for key, value in kwargs.items():
        if hasattr(ctx, key):
            setattr(ctx, key, value)
        else:
            ctx.metadata[key] = value
