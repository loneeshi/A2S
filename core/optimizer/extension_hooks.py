"""
Extension hook interface for the Auto-Expansion Agent framework.

Allows external code to:
1. Register callbacks that fire before/after tree extensions
2. Submit extension proposals programmatically
3. Receive notifications when extensions occur
"""

from typing import Protocol, List, Dict, Any, Optional, runtime_checkable
import logging

from .extension_engine import ExtensionProposal, ExtensionType
from ..generator.tree_builder import AgentTree


logger = logging.getLogger(__name__)


@runtime_checkable
class ExtensionHook(Protocol):
    """Protocol for extension lifecycle hooks."""

    def on_before_extension(
        self,
        tree: AgentTree,
        proposals: List[ExtensionProposal],
        performance_summary: Dict[str, Any],
    ) -> List[ExtensionProposal]:
        """
        Called before extensions are applied. Can filter/modify proposals.
        Return the (possibly modified) list of proposals to apply.
        """
        ...

    def on_after_extension(
        self,
        old_tree: AgentTree,
        new_tree: AgentTree,
        applied_proposals: List[ExtensionProposal],
        performance_summary: Dict[str, Any],
    ) -> None:
        """Called after extensions are applied."""
        ...


class ExtensionRegistry:
    """
    Registry for extension hooks and programmatic proposal submission.

    Usage:
        registry = ExtensionRegistry()
        registry.register_hook(my_hook)
        registry.submit_proposal(ExtensionProposal(...))
    """

    def __init__(self):
        self._hooks: List[ExtensionHook] = []
        self._pending_proposals: List[ExtensionProposal] = []

    def register_hook(self, hook: ExtensionHook) -> None:
        """Register an extension lifecycle hook."""
        self._hooks.append(hook)

    def unregister_hook(self, hook: ExtensionHook) -> None:
        """Unregister a hook."""
        self._hooks = [h for h in self._hooks if h is not hook]

    def submit_proposal(self, proposal: ExtensionProposal) -> None:
        """Submit an extension proposal programmatically (non-API path)."""
        self._pending_proposals.append(proposal)

    def drain_pending_proposals(self) -> List[ExtensionProposal]:
        """Pop all pending proposals (called by DynamicExtensionEngine)."""
        proposals = self._pending_proposals[:]
        self._pending_proposals.clear()
        return proposals

    def notify_before_extension(
        self,
        tree: AgentTree,
        proposals: List[ExtensionProposal],
        performance_summary: Dict[str, Any],
    ) -> List[ExtensionProposal]:
        """Notify all hooks before extension. Returns final proposal list."""
        current = proposals
        for hook in self._hooks:
            try:
                current = hook.on_before_extension(tree, current, performance_summary)
            except Exception as e:
                logger.warning(f"ExtensionHook.on_before_extension failed: {e}")
        return current

    def notify_after_extension(
        self,
        old_tree: AgentTree,
        new_tree: AgentTree,
        applied: List[ExtensionProposal],
        performance_summary: Dict[str, Any],
    ) -> None:
        """Notify all hooks after extension."""
        for hook in self._hooks:
            try:
                hook.on_after_extension(
                    old_tree, new_tree, applied, performance_summary
                )
            except Exception as e:
                logger.warning(f"ExtensionHook.on_after_extension failed: {e}")


_global_registry: Optional[ExtensionRegistry] = None


def get_extension_registry() -> ExtensionRegistry:
    """Get the global extension registry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ExtensionRegistry()
    return _global_registry
