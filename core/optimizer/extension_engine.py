"""
Dynamic Extension Engine for Auto-Expansion Agent Cluster

This module implements dynamic extension of agent trees during testing
based on performance feedback.

When performance is low, the engine:
1. Identifies the problem (missing tools, weak agents, uncovered tasks)
2. Generates extension proposals
3. Applies extensions to the tree
"""

from typing import Dict, List, Any, Optional
import logging
from enum import Enum

from ..generator.tree_builder import AgentTree, AgentDefinition
from .performance_monitor import PerformanceMonitor, TaskStatus


logger = logging.getLogger(__name__)


class ExtensionType(Enum):
    """Types of extensions that can be applied"""
    ADD_WORKER = "add_worker"
    ADD_TOOL_TO_WORKER = "add_tool_to_worker"
    SPECIALIZE_WORKER = "specialize_worker"
    ADD_MANAGER = "add_manager"
    REPLICATE_WORKER = "replicate_worker"


class ExtensionProposal:
    """Proposal for extending the agent tree"""

    def __init__(
        self,
        extension_type: ExtensionType,
        reason: str,
        priority: float,  # 0-1, higher = more important
        details: Dict[str, Any]
    ):
        self.extension_type = extension_type
        self.reason = reason
        self.priority = priority
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.extension_type.value,
            "reason": self.reason,
            "priority": self.priority,
            "details": self.details,
        }


class DynamicExtensionEngine:
    """
    Dynamically extend agent trees based on performance feedback

    Process:
    1. Monitor performance (done by PerformanceMonitor)
    2. Detect when extension is needed
    3. Analyze problems and generate proposals
    4. Apply highest-priority extensions
    5. Verify improvements
    """

    def __init__(
        self,
        performance_monitor: PerformanceMonitor,
        extension_threshold: float = 0.7,
        max_workers: int = 20,
        max_managers: int = 5
    ):
        """
        Initialize the extension engine

        Args:
            performance_monitor: Performance monitor instance
            extension_threshold: Success rate below which to trigger extension
            max_workers: Maximum number of workers to create
            max_managers: Maximum number of managers to create
        """
        self.performance_monitor = performance_monitor
        self.extension_threshold = extension_threshold
        self.max_workers = max_workers
        self.max_managers = max_managers
        self.extension_history: List[Dict[str, Any]] = []

    def monitor_and_extend(
        self,
        tree: AgentTree,
        last_task_result: Optional[Any] = None
    ) -> AgentTree:
        """
        Monitor performance and extend tree if needed

        Args:
            tree: Current agent tree
            last_task_result: Optional last task result

        Returns:
            Extended tree (or original if no extension needed)
        """
        # Check if extension is needed
        if not self.performance_monitor.should_trigger_extension(self.extension_threshold):
            return tree

        logger.info("Performance threshold breached, analyzing for extension...")

        # Generate extension proposals
        proposals = self._generate_extension_proposals(tree)

        if not proposals:
            logger.info("No extension proposals generated")
            return tree

        # Sort by priority
        proposals.sort(key=lambda p: p.priority, reverse=True)

        # Apply top N proposals
        num_to_apply = min(3, len(proposals))  # Apply up to 3 extensions
        extended_tree = tree
        for proposal in proposals[:num_to_apply]:
            logger.info(f"Applying extension: {proposal.extension_type.value}")
            extended_tree = self._apply_extension(extended_tree, proposal)
            self.extension_history.append(proposal.to_dict())

        logger.info(f"Applied {num_to_apply} extensions")
        return extended_tree

    def _generate_extension_proposals(
        self,
        tree: AgentTree
    ) -> List[ExtensionProposal]:
        """
        Analyze performance and generate extension proposals

        Args:
            tree: Current agent tree

        Returns:
            List of ExtensionProposal objects
        """
        proposals = []

        # Check for difficult task types
        summary = self.performance_monitor.get_summary()
        difficult_tasks = [
            task_type for task_type, metrics in summary["task_type_metrics"].items()
            if metrics["success_rate"] < 0.5
        ]

        for task_type in difficult_tasks:
            metrics = summary["task_type_metrics"][task_type]
            # High priority for very low success rates
            priority = 1.0 - metrics["success_rate"]

            proposal = ExtensionProposal(
                extension_type=ExtensionType.ADD_WORKER,
                reason=f"Task type '{task_type}' has low success rate ({metrics['success_rate']:.2f})",
                priority=priority,
                details={
                    "task_type": task_type,
                    "current_success_rate": metrics["success_rate"],
                    "specialization": task_type,
                }
            )
            proposals.append(proposal)

        # Check for underperforming agents
        underperforming = self.performance_monitor.get_underperforming_agents(
            threshold=self.extension_threshold
        )

        for agent_name in underperforming:
            agent_metrics = self.performance_monitor.get_agent_performance(agent_name)
            if agent_metrics and agent_metrics.total_tasks >= 5:  # Only if enough data
                # Proposal: specialize or replicate
                priority = 1.0 - agent_metrics.success_rate

                # Find the most common failing task type for this agent
                failing_tasks = [
                    task_type for task_type, count in agent_metrics.task_types.items()
                    # (In reality, we'd check which tasks are failing)
                ]

                if failing_tasks:
                    proposal = ExtensionProposal(
                        extension_type=ExtensionType.SPECIALIZE_WORKER,
                        reason=f"Agent '{agent_name}' underperforming (success rate: {agent_metrics.success_rate:.2f})",
                        priority=priority,
                        details={
                            "agent_name": agent_name,
                            "current_success_rate": agent_metrics.success_rate,
                            "specialization": failing_tasks[0],
                        }
                    )
                else:
                    proposal = ExtensionProposal(
                        extension_type=ExtensionType.REPLICATE_WORKER,
                        reason=f"Agent '{agent_name}' overloaded (success rate: {agent_metrics.success_rate:.2f})",
                        priority=priority * 0.8,  # Lower priority than specialization
                        details={
                            "agent_to_replicate": agent_name,
                            "current_success_rate": agent_metrics.success_rate,
                        }
                    )
                proposals.append(proposal)

        # Check if we need more managers (many workers)
        if len(tree.workers) > 8 and len(tree.managers) < self.max_managers:
            proposal = ExtensionProposal(
                extension_type=ExtensionType.ADD_MANAGER,
                reason=f"Many workers ({len(tree.workers)}) but few managers ({len(tree.managers)})",
                priority=0.6,
                details={
                    "num_workers": len(tree.workers),
                    "num_managers": len(tree.managers),
                    "manager_type": "coordinator",
                }
            )
            proposals.append(proposal)

        return proposals

    def _apply_extension(
        self,
        tree: AgentTree,
        proposal: ExtensionProposal
    ) -> AgentTree:
        """
        Apply an extension proposal to the tree

        Args:
            tree: Current agent tree
            proposal: Extension proposal to apply

        Returns:
            Extended tree
        """
        if proposal.extension_type == ExtensionType.ADD_WORKER:
            return self._add_worker(tree, proposal.details)
        elif proposal.extension_type == ExtensionType.SPECIALIZE_WORKER:
            return self._specialize_worker(tree, proposal.details)
        elif proposal.extension_type == ExtensionType.REPLICATE_WORKER:
            return self._replicate_worker(tree, proposal.details)
        elif proposal.extension_type == ExtensionType.ADD_MANAGER:
            return self._add_manager(tree, proposal.details)
        else:
            logger.warning(f"Unknown extension type: {proposal.extension_type}")
            return tree

    def _add_worker(self, tree: AgentTree, details: Dict[str, Any]) -> AgentTree:
        """Add a new specialized worker"""
        if len(tree.workers) >= self.max_workers:
            logger.warning(f"Max workers ({self.max_workers}) reached, not adding worker")
            return tree

        task_type = details.get("specialization", "general")
        worker_name = f"{task_type.capitalize()}Worker{len(tree.workers)}"

        new_worker = AgentDefinition(
            name=worker_name,
            role="worker",
            domain=task_type,
            tools=[],  # Will be populated based on task type
            prompt=None,  # Will be created by prompt builder
            metadata={
                "added_by": "extension_engine",
                "specialization": task_type,
                "reason": details.get("reason", ""),
            }
        )

        new_workers = tree.workers + [new_worker]
        return AgentTree(
            workers=new_workers,
            managers=tree.managers,
            metadata=tree.metadata
        )

    def _specialize_worker(self, tree: AgentTree, details: Dict[str, Any]) -> AgentTree:
        """Specialize an existing worker for a specific task type"""
        agent_name = details.get("agent_name")
        specialization = details.get("specialization")

        # Find the worker and update it
        updated_workers = []
        for worker in tree.workers:
            if worker.name == agent_name:
                # Create specialized version
                specialized = AgentDefinition(
                    name=f"{worker.name}_{specialization}",
                    role=worker.role,
                    domain=specialization,
                    tools=worker.tools,
                    prompt=worker.prompt,
                    metadata={
                        **worker.metadata,
                        "specialized": True,
                        "specialization": specialization,
                        "parent_agent": agent_name,
                    }
                )
                updated_workers.append(specialized)
            else:
                updated_workers.append(worker)

        return AgentTree(
            workers=updated_workers,
            managers=tree.managers,
            metadata=tree.metadata
        )

    def _replicate_worker(self, tree: AgentTree, details: Dict[str, Any]) -> AgentTree:
        """Replicate an existing worker"""
        if len(tree.workers) >= self.max_workers:
            logger.warning(f"Max workers ({self.max_workers}) reached, not replicating")
            return tree

        agent_name = details.get("agent_to_replicate")

        # Find the worker and replicate it
        for worker in tree.workers:
            if worker.name == agent_name:
                replica = AgentDefinition(
                    name=f"{worker.name}_replica{len(tree.workers)}",
                    role=worker.role,
                    domain=worker.domain,
                    tools=worker.tools,
                    prompt=worker.prompt,
                    metadata={
                        **worker.metadata,
                        "replica": True,
                        "parent_agent": agent_name,
                    }
                )
                new_workers = tree.workers + [replica]
                return AgentTree(
                    workers=new_workers,
                    managers=tree.managers,
                    metadata=tree.metadata
                )

        return tree

    def _add_manager(self, tree: AgentTree, details: Dict[str, Any]) -> AgentTree:
        """Add a new manager"""
        if len(tree.managers) >= self.max_managers:
            logger.warning(f"Max managers ({self.max_managers}) reached, not adding manager")
            return tree

        manager_type = details.get("manager_type", "coordinator")
        manager_name = f"{manager_type.capitalize()}Manager{len(tree.managers)}"

        new_manager = AgentDefinition(
            name=manager_name,
            role="manager",
            domain="general",
            tools=[],
            prompt=None,
            metadata={
                "added_by": "extension_engine",
                "manager_type": manager_type,
                "reason": details.get("reason", ""),
            }
        )

        new_managers = tree.managers + [new_manager]
        return AgentTree(
            workers=tree.workers,
            managers=new_managers,
            metadata=tree.metadata
        )

    def get_extension_history(self) -> List[Dict[str, Any]]:
        """Get history of all extensions applied"""
        return self.extension_history.copy()

    def reset_history(self) -> None:
        """Reset extension history"""
        self.extension_history.clear()
        logger.info("Extension history reset")
