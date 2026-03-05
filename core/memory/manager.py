"""
Memory Manager for Auto-Expansion Agent Cluster.

Provides short-term (in-memory rolling window), long-term (JSON file persistence),
and reflection memory storage with retrieval via SemanticRouter.
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .schema import MemoryEntry, ReflectionMemoryEntry, MemoryQuery, MemoryType
from .router import SemanticRouter
from .semantic_cache import SemanticCache

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified memory manager supporting short-term, long-term, and reflection tiers.

    Short-term: in-memory rolling window per agent (last N entries).
    Long-term / Reflection: JSON-file persistence under store/{long_term,reflection}/.
    Retrieval: routed through SemanticRouter for scored ranking.
    """

    def __init__(
        self,
        store_dir: Optional[Path] = None,
        short_term_capacity: int = 50,
    ):
        if store_dir is None:
            store_dir = Path(__file__).parent / "store"
        self.store_dir = Path(store_dir)
        self.long_term_dir = self.store_dir / "long_term"
        self.reflection_dir = self.store_dir / "reflection"
        self.long_term_dir.mkdir(parents=True, exist_ok=True)
        self.reflection_dir.mkdir(parents=True, exist_ok=True)

        self.short_term_capacity = short_term_capacity
        self._short_term: Dict[str, List[MemoryEntry]] = {}
        self._router = SemanticRouter()
        self._semantic_cache = SemanticCache()

        logger.info(
            f"MemoryManager initialized (store={self.store_dir}, "
            f"short_term_capacity={short_term_capacity})"
        )

    def store(self, entry: MemoryEntry) -> None:
        """
        Store a memory entry in the appropriate tier.

        SHORT_TERM/WORKING → in-memory rolling window keyed by agent_name.
        LONG_TERM → persisted to JSON file.
        REFLECTION → persisted to JSON file (use store_reflection for ReflectionMemoryEntry).
        """
        if entry.memory_type in (MemoryType.SHORT_TERM, MemoryType.WORKING):
            self._store_short_term(entry)
        elif entry.memory_type == MemoryType.LONG_TERM:
            self._persist_entry(self.long_term_dir, entry)
        elif entry.memory_type == MemoryType.REFLECTION:
            self._persist_entry(self.reflection_dir, entry)
        else:
            logger.warning(f"Unknown memory type: {entry.memory_type}")

    def store_reflection(self, entry: ReflectionMemoryEntry) -> None:
        """Store a structured reflection memory entry."""
        entry.memory_type = MemoryType.REFLECTION
        self._persist_entry(self.reflection_dir, entry)

    def retrieve(self, query: MemoryQuery) -> List[MemoryEntry]:
        """
        Retrieve memories matching a query, ranked by SemanticRouter.

        Combines in-memory short-term and on-disk long-term/reflection entries,
        then routes through SemanticRouter for scored ranking.
        """
        # Semantic cache lookup (boost cache hit rate)
        cached = self._semantic_cache.lookup(query)
        if cached is not None:
            return cached

        candidates: List[MemoryEntry] = []

        if query.memory_type is None or query.memory_type == MemoryType.SHORT_TERM:
            for entries in self._short_term.values():
                candidates.extend(entries)

        if query.memory_type is None or query.memory_type == MemoryType.LONG_TERM:
            candidates.extend(self._load_persisted(self.long_term_dir))

        if query.memory_type is None or query.memory_type == MemoryType.REFLECTION:
            candidates.extend(
                self._load_persisted(self.reflection_dir, reflection=True)
            )

        results = self._router.route(query, candidates)
        self._semantic_cache.store(query, results)
        return results

    def get_short_term(self, agent_name: str) -> List[MemoryEntry]:
        """Get the short-term memory window for a specific agent."""
        return list(self._short_term.get(agent_name, []))

    def get_working_context(
        self,
        agent_name: str,
        domain: str,
        task_type: str,
    ) -> Dict[str, Any]:
        """
        Build a working context dict for prompt injection.

        Returns:
            Dict with keys: recent_actions, lessons_learned, known_errors.
        """
        recent = self.get_short_term(agent_name)
        recent_actions = [e.content for e in recent[-10:]]

        lesson_query = MemoryQuery(
            domain=domain,
            task_type=task_type,
            memory_type=MemoryType.LONG_TERM,
            tags=["lesson"],
            limit=5,
        )
        lessons = self.retrieve(lesson_query)
        lessons_learned = [e.content for e in lessons]

        error_query = MemoryQuery(
            domain=domain,
            task_type=task_type,
            memory_type=MemoryType.REFLECTION,
            limit=5,
        )
        errors = self.retrieve(error_query)
        known_errors = []
        for e in errors:
            if isinstance(e, ReflectionMemoryEntry):
                known_errors.append(
                    {
                        "failure_type": e.failure_type,
                        "root_cause": e.root_cause,
                        "tools": e.tools_involved,
                    }
                )
            else:
                known_errors.append({"content": e.content})

        return {
            "recent_actions": recent_actions,
            "lessons_learned": lessons_learned,
            "known_errors": known_errors,
        }

    def prune_expired(self) -> int:
        """Remove expired entries from all tiers. Returns count of pruned entries."""
        pruned = 0

        for agent, entries in self._short_term.items():
            before = len(entries)
            self._short_term[agent] = [e for e in entries if not e.is_expired()]
            pruned += before - len(self._short_term[agent])

        for directory in (self.long_term_dir, self.reflection_dir):
            for fpath in directory.glob("*.json"):
                try:
                    data = json.loads(fpath.read_text())
                    entry = MemoryEntry.from_dict(data)
                    if entry.is_expired():
                        fpath.unlink()
                        pruned += 1
                except Exception:
                    pass

        if pruned:
            logger.info(f"Pruned {pruned} expired memory entries")
        return pruned

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics across all memory tiers."""
        short_count = sum(len(v) for v in self._short_term.values())
        long_count = len(list(self.long_term_dir.glob("*.json")))
        refl_count = len(list(self.reflection_dir.glob("*.json")))

        return {
            "short_term_entries": short_count,
            "short_term_agents": len(self._short_term),
            "long_term_entries": long_count,
            "reflection_entries": refl_count,
            "total_entries": short_count + long_count + refl_count,
        }

    def _store_short_term(self, entry: MemoryEntry) -> None:
        agent = entry.agent_name
        if agent not in self._short_term:
            self._short_term[agent] = []
        self._short_term[agent].append(entry)
        if len(self._short_term[agent]) > self.short_term_capacity:
            self._short_term[agent] = self._short_term[agent][
                -self.short_term_capacity :
            ]

    def _persist_entry(self, directory: Path, entry: MemoryEntry) -> None:
        fpath = directory / f"{entry.entry_id}.json"
        fpath.write_text(json.dumps(entry.to_dict(), indent=2))
        logger.debug(f"Persisted {entry.memory_type.value} entry: {fpath.name}")

    def _load_persisted(
        self, directory: Path, reflection: bool = False
    ) -> List[MemoryEntry]:
        entries: List[MemoryEntry] = []
        for fpath in directory.glob("*.json"):
            try:
                data = json.loads(fpath.read_text())
                if reflection:
                    entries.append(ReflectionMemoryEntry.from_dict(data))
                else:
                    entries.append(MemoryEntry.from_dict(data))
            except Exception as e:
                logger.warning(f"Failed to load {fpath}: {e}")
        return entries


_memory_manager_instance: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get singleton MemoryManager instance."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance
