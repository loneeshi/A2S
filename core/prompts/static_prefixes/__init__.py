"""
Static Prefixes for Auto-Expansion Agent Cluster

This module contains static prefixes for different domains.
Each static prefix is designed to maximize cache hit rates by providing
consistent, reusable content that appears first in prompts.

Static prefixes are shared across:
- All agents within a domain (workers and managers)
- All tasks within a domain
- Multiple benchmark instances

Expected cache hit rate: 70-80% (first 1024 tokens identical)

Usage:
    from core.prompts.static_prefixes.navigation import NAVIGATION_STATIC_PREFIX
    from core.prompts.static_prefixes.email import EMAIL_STATIC_PREFIX
    from core.prompts.static_prefixes.course import COURSE_STATIC_PREFIX
"""

from .navigation import NAVIGATION_STATIC_PREFIX
from .email import EMAIL_STATIC_PREFIX
from .course import COURSE_STATIC_PREFIX

__all__ = [
    "NAVIGATION_STATIC_PREFIX",
    "EMAIL_STATIC_PREFIX",
    "COURSE_STATIC_PREFIX",
]

# Domain mapping for dynamic loading
DOMAIN_PREFIXES = {
    "navigation": NAVIGATION_STATIC_PREFIX,
    "email": EMAIL_STATIC_PREFIX,
    "course": COURSE_STATIC_PREFIX,
}


def get_static_prefix(domain: str) -> str:
    """
    Get static prefix for a domain

    Args:
        domain: Domain name (e.g., "navigation", "email", "course")

    Returns:
        Static prefix string for the domain

    Raises:
        ValueError: If domain not found
    """
    if domain not in DOMAIN_PREFIXES:
        available = ", ".join(DOMAIN_PREFIXES.keys())
        raise ValueError(
            f"Unknown domain: '{domain}'. Available domains: {available}"
        )
    return DOMAIN_PREFIXES[domain]
