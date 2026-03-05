"""
Semantic Router for Memory Retrieval.

Lightweight metadata-based routing for memory retrieval.
Uses field matching + tag overlap scoring — no embedding dependencies.
"""

import logging
from datetime import datetime
from typing import List

from .schema import MemoryEntry, MemoryQuery

logger = logging.getLogger(__name__)


class SemanticRouter:
    """
    Lightweight semantic routing for memory retrieval.

    Uses metadata field matching + tag overlap scoring.
    No embedding dependencies.
    """

    def route(
        self, query: MemoryQuery, entries: List[MemoryEntry]
    ) -> List[MemoryEntry]:
        """
        Filter and rank entries against query.

        Scoring: exact field matches + tag overlap + importance + recency.
        Returns sorted list (best match first), limited to query.limit.

        Args:
            query: Retrieval query with filter fields.
            entries: Candidate memory entries to score.

        Returns:
            Filtered and ranked list of entries.
        """
        scored = []
        for entry in entries:
            if not self._passes_filters(query, entry):
                continue
            score = self._score_entry(query, entry)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = [entry for _, entry in scored[: query.limit]]
        logger.debug(
            f"SemanticRouter: {len(entries)} candidates -> "
            f"{len(results)} results (query domain={query.domain})"
        )
        return results

    def _passes_filters(self, query: MemoryQuery, entry: MemoryEntry) -> bool:
        """Check hard filters that disqualify an entry."""
        if not query.include_expired and entry.is_expired():
            return False
        if entry.importance < query.min_importance:
            return False
        if query.memory_type is not None and entry.memory_type != query.memory_type:
            return False
        if query.agent_name is not None and entry.agent_name != query.agent_name:
            return False
        return True

    def _score_entry(self, query: MemoryQuery, entry: MemoryEntry) -> float:
        """
        Score an entry against a query.

        Scoring breakdown:
        - +3.0 for exact domain match
        - +2.0 for exact task_type match
        - +1.0 per matching tag
        - +importance (0.0–1.0)
        - +recency bonus (newer = higher, max 1.0)

        Args:
            query: Retrieval query.
            entry: Memory entry to score.

        Returns:
            Numeric relevance score.
        """
        score = 0.0

        if query.domain is not None and entry.domain == query.domain:
            score += 3.0

        if query.task_type is not None and entry.task_type == query.task_type:
            score += 2.0

        if query.tags:
            query_tags = set(query.tags)
            entry_tags = set(entry.tags)
            score += len(query_tags & entry_tags)

        score += entry.importance

        score += self._recency_bonus(entry.created_at)

        return score

    @staticmethod
    def _recency_bonus(
        created_at: str, max_bonus: float = 1.0, half_life_hours: float = 24.0
    ) -> float:
        """
        Compute a recency bonus that decays over time.

        Uses exponential decay with a configurable half-life.
        Entries created now get max_bonus; entries older than ~3 half-lives get ~0.

        Args:
            created_at: ISO format timestamp of entry creation.
            max_bonus: Maximum recency bonus.
            half_life_hours: Hours until bonus halves.

        Returns:
            Recency bonus in [0, max_bonus].
        """
        try:
            created = datetime.fromisoformat(created_at)
            age_hours = (datetime.utcnow() - created).total_seconds() / 3600
            if age_hours < 0:
                age_hours = 0
        except (ValueError, TypeError):
            return 0.0

        import math

        decay = math.exp(-0.693 * age_hours / half_life_hours)  # ln(2) ≈ 0.693
        return max_bonus * decay
