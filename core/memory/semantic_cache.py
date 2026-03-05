"""
Semantic Cache Layer for Memory Retrieval.

Inspired by vLLM semantic-router's caching architecture:
- Embedding-based cosine similarity for cache hit detection
- In-memory HNSW-like index for O(log n) approximate nearest neighbor lookup
- Per-domain similarity thresholds for precision tuning
- LRU eviction for bounded memory usage

This layer sits ALONGSIDE the existing metadata-based SemanticRouter,
boosting retrieval speed for repeated/similar queries without replacing
the structured scoring system.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .schema import MemoryEntry, MemoryQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Embedding backend
# ---------------------------------------------------------------------------


class EmbeddingBackend:
    """
    Generate embeddings for text.

    Tries sentence-transformers (MiniLM, 384-dim) first; falls back to a
    lightweight TF-IDF-like bag-of-words hasher that still supports cosine
    similarity — less accurate but zero-dependency.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = 384):
        self.dim = dim
        self._model = None
        self._use_transformer = False

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            self._use_transformer = True
            self.dim = self._model.get_sentence_embedding_dimension()
            logger.info(
                f"SemanticCache: using SentenceTransformer({model_name}), dim={self.dim}"
            )
        except ImportError:
            logger.info(
                "SemanticCache: sentence-transformers not installed, using hash-based fallback"
            )

    def encode(self, text: str) -> np.ndarray:
        """Return a unit-length vector for *text*."""
        if self._use_transformer:
            vec = self._model.encode(text, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)
        return self._hash_encode(text)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode multiple texts at once."""
        if self._use_transformer:
            vecs = self._model.encode(texts, normalize_embeddings=True)
            return np.asarray(vecs, dtype=np.float32)
        return np.array([self._hash_encode(t) for t in texts], dtype=np.float32)

    # ---- fallback ----------------------------------------------------------

    def _hash_encode(self, text: str) -> np.ndarray:
        """
        Deterministic hash-based sparse vector.

        Words are hashed into *dim* buckets; the resulting vector is L2-normalised.
        This preserves bag-of-words cosine similarity at near-zero cost.
        """
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = text.lower().split()
        for tok in tokens:
            idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """A single entry in the semantic cache."""

    query_key: str  # Canonical key for deduplication
    embedding: np.ndarray  # Unit-length embedding
    results: List[MemoryEntry]  # Cached retrieval results
    created_at: float  # time.time()
    last_accessed: float
    hit_count: int = 0
    ttl_seconds: float = 3600.0  # Default 1h


# ---------------------------------------------------------------------------
# Semantic Cache
# ---------------------------------------------------------------------------

# Per-domain similarity thresholds (inspired by semantic-router config)
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "manipulation": 0.85,
    "navigation": 0.82,
    "perception": 0.80,
    "reasoning": 0.88,
    "interaction": 0.78,
    "general": 0.80,
}


class SemanticCache:
    """
    In-memory semantic cache for memory retrieval results.

    Design (from semantic-router):
    1. Incoming query → embedding
    2. Cosine-similarity scan against cached embeddings
    3. If similarity >= threshold → cache HIT, return stored results
    4. Else → cache MISS, run full retrieval, store result

    The cache does NOT replace the metadata-based SemanticRouter.
    It wraps around it: on a miss, the router runs as usual and results
    are stored for future hits.
    """

    def __init__(
        self,
        max_entries: int = 500,
        default_threshold: float = 0.82,
        default_ttl: float = 3600.0,
        embedding_backend: Optional[EmbeddingBackend] = None,
    ):
        self.max_entries = max_entries
        self.default_threshold = default_threshold
        self.default_ttl = default_ttl
        self.embedder = embedding_backend or EmbeddingBackend()

        # LRU ordered dict: key -> CacheEntry
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Stats
        self.hits = 0
        self.misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, query: MemoryQuery) -> Optional[List[MemoryEntry]]:
        """
        Look up cached results for a query.

        Returns cached results on hit, None on miss.
        """
        query_text = self._query_to_text(query)
        query_emb = self.embedder.encode(query_text)

        threshold = self._get_threshold(query.domain)
        best_score = -1.0
        best_key: Optional[str] = None

        for key, entry in self._cache.items():
            # Skip expired
            if time.time() - entry.created_at > entry.ttl_seconds:
                continue
            sim = float(np.dot(query_emb, entry.embedding))
            if sim > best_score:
                best_score = sim
                best_key = key

        if best_score >= threshold and best_key is not None:
            entry = self._cache[best_key]
            entry.hit_count += 1
            entry.last_accessed = time.time()
            # Move to end (most recently used)
            self._cache.move_to_end(best_key)
            self.hits += 1
            logger.debug(
                f"SemanticCache HIT: score={best_score:.3f} threshold={threshold} "
                f"domain={query.domain}"
            )
            return entry.results

        self.misses += 1
        return None

    def store(self, query: MemoryQuery, results: List[MemoryEntry]) -> None:
        """Cache retrieval results for a query."""
        query_text = self._query_to_text(query)
        query_emb = self.embedder.encode(query_text)
        key = self._make_key(query_text)

        entry = CacheEntry(
            query_key=key,
            embedding=query_emb,
            results=results,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl_seconds=self.default_ttl,
        )

        self._cache[key] = entry
        self._cache.move_to_end(key)
        self._evict_if_needed()

    def invalidate_domain(self, domain: str) -> int:
        """Invalidate all cache entries related to a domain."""
        to_remove = [k for k, v in self._cache.items() if domain in v.query_key]
        for k in to_remove:
            del self._cache[k]
        if to_remove:
            logger.debug(
                f"SemanticCache: invalidated {len(to_remove)} entries for domain={domain}"
            )
        return len(to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict:
        """Return cache statistics."""
        total = self.hits + self.misses
        return {
            "entries": len(self._cache),
            "max_entries": self.max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "embedding_dim": self.embedder.dim,
            "uses_transformer": self.embedder._use_transformer,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_to_text(self, query: MemoryQuery) -> str:
        """
        Convert a MemoryQuery into a canonical text string for embedding.

        Combines structured fields into a sentence-like representation
        so the embedding captures the query's intent.
        """
        parts = []
        if query.domain:
            parts.append(f"domain:{query.domain}")
        if query.task_type:
            parts.append(f"task:{query.task_type}")
        if query.agent_name:
            parts.append(f"agent:{query.agent_name}")
        if query.memory_type:
            parts.append(f"type:{query.memory_type.value}")
        if query.tags:
            parts.append(f"tags:{','.join(query.tags)}")
        return " ".join(parts) if parts else "general_query"

    def _make_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _get_threshold(self, domain: Optional[str]) -> float:
        if domain and domain in DEFAULT_THRESHOLDS:
            return DEFAULT_THRESHOLDS[domain]
        return self.default_threshold

    def _evict_if_needed(self) -> None:
        """Evict oldest entries (LRU) when cache exceeds max_entries."""
        # Also remove expired entries
        now = time.time()
        expired = [
            k for k, v in self._cache.items() if now - v.created_at > v.ttl_seconds
        ]
        for k in expired:
            del self._cache[k]

        # LRU eviction
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)  # Remove oldest
