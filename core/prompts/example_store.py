"""
Example Store for Dynamic Few-Shot Learning.

Uses SemanticCache (Faiss HNSW) to index successful task trajectories.
Retrieves relevant examples for new tasks to boost performance via In-Context Learning.
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from core.memory.semantic_cache import SemanticCache, EmbeddingBackend
from core.memory.schema import MemoryEntry, MemoryQuery, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class Example:
    """A successful task execution example."""

    task_description: str
    trajectory: str  # Formatted history of actions/observations
    domain: str
    score: float = 1.0
    metadata: Dict[str, Any] = None


class ExampleStore:
    """
    Store and retrieve successful examples for few-shot prompting.
    """

    def __init__(self, persist_dir: str = "data/examples"):
        self.persist_dir = persist_dir
        # Reuse SemanticCache for efficient embedding search
        # We map "task_description" -> "query", and "trajectory" -> "result"
        self.cache = SemanticCache(
            persist_dir=persist_dir,
            max_entries=1000,  # Keep high-quality examples
            default_threshold=0.75,  # Slightly lower threshold for broader relevance
            default_ttl=31536000.0,  # 1 year (long-term knowledge)
        )

    def add_example(self, example: Example):
        """Add a successful example to the store."""
        # Wrap as MemoryEntry for compatibility with SemanticCache
        entry = MemoryEntry(
            entry_id=f"ex-{hash(example.task_description)}",
            memory_type=MemoryType.LONG_TERM,
            domain=example.domain,
            task_type="example",
            agent_name="system",
            created_at=str(time.time()),
            content=example.trajectory,
            tags=["example", example.domain],
            importance=example.score,
            metadata={"task": example.task_description, **(example.metadata or {})},
        )

        # Query is the task description
        query = MemoryQuery(
            domain=example.domain,
            task_type="example",
            content=example.task_description,  # This gets embedded
        )

        self.cache.store(query, [entry])
        logger.info(f"Stored example for domain '{example.domain}'")

    def retrieve_relevant(
        self, task_description: str, domain: str, k: int = 3
    ) -> List[Example]:
        """Retrieve top-k relevant examples for a task."""
        query = MemoryQuery(
            domain=domain, task_type="example", content=task_description
        )

        # SemanticCache returns list of MemoryEntry
        # We need to hack it a bit: SemanticCache.lookup usually returns EXACT matches or high sim
        # But we want top-k. The current SemanticCache.lookup returns the *best* match's results.
        # To support RAG properly, we might need to expose index.search directly or accept list.

        # Current SemanticCache logic:
        # lookup -> finds nearest cluster -> returns that cluster's entries.
        # This works if we store 1 example per "cluster" (query key).

        results = self.cache.lookup(query)
        if not results:
            return []

        examples = []
        for entry in results[:k]:
            examples.append(
                Example(
                    task_description=entry.metadata.get("task", ""),
                    trajectory=entry.content,
                    domain=entry.domain,
                    score=entry.importance,
                    metadata=entry.metadata,
                )
            )

        return examples


import time
