"""
Semantic Cache Layer with Faiss HNSW Indexing.

Advanced Features:
- Faiss HNSW Index: O(log n) approximate nearest neighbor search
- Persistence: Saves/loads index and data to disk
- Domain-Adaptive Thresholds: Custom similarity per domain
- LRU Eviction: Keeps index size manageable
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

import numpy as np

try:
    import faiss
except ImportError:
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from .schema import MemoryEntry, MemoryQuery

logger = logging.getLogger(__name__)


class EmbeddingBackend:
    """
    Generate embeddings for text.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = 384):
        self.dim = dim
        self._model = None
        self._use_transformer = False

        if SentenceTransformer:
            try:
                self._model = SentenceTransformer(model_name)
                self._use_transformer = True
                self.dim = self._model.get_sentence_embedding_dimension()
                logger.info(
                    "SemanticCache: using SentenceTransformer(%s), dim=%s",
                    model_name,
                    self.dim,
                )
            except Exception as e:
                logger.warning("Failed to load SentenceTransformer: %s", e)

        if not self._use_transformer:
            logger.info(
                "SemanticCache: sentence-transformers not available; using hash fallback"
            )

    def encode(self, text: str) -> np.ndarray:
        """Return a unit-length embedding vector for text."""
        if self._use_transformer and self._model:
            vec = self._model.encode(text, normalize_embeddings=True)
            return np.asarray(vec, dtype=np.float32)
        return self._hash_encode(text)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        if self._use_transformer and self._model:
            vecs = self._model.encode(texts, normalize_embeddings=True)
            return np.asarray(vecs, dtype=np.float32)
        return np.array([self._hash_encode(text) for text in texts], dtype=np.float32)

    def _hash_encode(self, text: str) -> np.ndarray:
        """
        Deterministic hash-based sparse vector with L2 normalization.
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


@dataclass
class CacheEntry:
    query_key: str
    embedding: List[float]  # JSON serializable
    results: List[Dict[str, Any]]  # Serialized MemoryEntry
    created_at: float
    last_accessed: float
    hit_count: int = 0
    ttl_seconds: float = 3600.0


# Domain-Specific Thresholds (tuned for precision/recall balance)
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "manipulation": 0.85,  # High precision needed for physical actions
    "navigation": 0.82,  # Slightly relaxed for spatial queries
    "perception": 0.80,  # Tolerant to visual descriptions variations
    "reasoning": 0.88,  # Strict logic matching
    "interaction": 0.78,  # Flexible conversation matching
    "general": 0.80,
}


class SemanticCache:
    """
    Persistent Semantic Cache with Faiss HNSW Index.
    """

    def __init__(
        self,
        persist_dir: str = "data/cache",
        max_entries: int = 5000,
        default_threshold: float = 0.82,
        default_ttl: float = 86400.0,  # 24 hours default
        embedding_backend: Optional[EmbeddingBackend] = None,
    ):
        self.persist_dir = persist_dir
        self.max_entries = max_entries
        self.default_threshold = default_threshold
        self.default_ttl = default_ttl
        self.embedder = embedding_backend or EmbeddingBackend()

        self.index_path = os.path.join(persist_dir, "semantic_index.faiss")
        self.data_path = os.path.join(persist_dir, "cache_data.json")

        # Ensure persist dir exists
        os.makedirs(persist_dir, exist_ok=True)

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0

        # Faiss Index Initialization
        self.use_faiss = faiss is not None
        self.index: Any = None
        self.id_to_key: Dict[int, str] = {}
        self.next_id = 0

        if self.use_faiss and faiss:
            self._init_faiss_index()
        else:
            logger.warning("Faiss not installed. Falling back to linear scan (slow).")

        # Load persisted data
        self._load()

    def _init_faiss_index(self):
        """Initialize Faiss HNSW index."""
        if not faiss:
            return
        # HNSW params: M=16 neighbors, efConstruction=200 quality
        self.index = faiss.IndexHNSWFlat(self.embedder.dim, 16)
        self.index.hnsw.efConstruction = 200
        self.index.hnsw.efSearch = 50  # Search quality

    def lookup(self, query: MemoryQuery) -> Optional[List[MemoryEntry]]:
        query_text = self._query_to_text(query)
        query_emb = self.embedder.encode(query_text)
        threshold = self._get_threshold(query.domain)

        # 1. Faiss Search (O(log n))
        if self.use_faiss and self.index and self.index.ntotal > 0:
            k = min(10, self.index.ntotal)  # Check top 10 candidates
            # Reshape for Faiss (1, dim)
            q_vec = query_emb.reshape(1, -1)
            distances, indices = self.index.search(q_vec, k)

            # Check candidates
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    continue
                # Inner Product distance is cosine similarity for normalized vectors
                similarity = dist

                if similarity >= threshold:
                    key = self.id_to_key.get(int(idx))
                    if key and key in self._cache:
                        entry = self._cache[key]
                        # Check TTL
                        if time.time() - entry.created_at <= entry.ttl_seconds:
                            self._record_hit(key)
                            return [MemoryEntry(**r) for r in entry.results]

        # 2. Linear Fallback (if Faiss fails or not used)
        if not self.use_faiss or not self.index:
            best_score = -1.0
            best_key = None

            for key, entry in self._cache.items():
                if time.time() - entry.created_at > entry.ttl_seconds:
                    continue
                # Recalculate similarity (slow)
                emb = np.array(entry.embedding, dtype=np.float32)
                sim = float(np.dot(query_emb, emb))

                if sim > best_score:
                    best_score = sim
                    best_key = key

            if best_key and best_score >= threshold:
                self._record_hit(best_key)
                return [MemoryEntry(**r) for r in self._cache[best_key].results]

        self.misses += 1
        return None

    def store(self, query: MemoryQuery, results: List[MemoryEntry]) -> None:
        query_text = self._query_to_text(query)
        query_emb = self.embedder.encode(query_text)
        key = self._make_key(query_text)

        # Prepare entry
        entry = CacheEntry(
            query_key=key,
            embedding=query_emb.tolist(),
            results=[asdict(r) for r in results],
            created_at=time.time(),
            last_accessed=time.time(),
            ttl_seconds=self.default_ttl,
        )

        self._cache[key] = entry
        self._cache.move_to_end(key)

        # Add to Faiss
        if self.use_faiss and self.index:
            self.index.add(query_emb.reshape(1, -1))
            self.id_to_key[self.next_id] = key
            self.next_id += 1

        self._evict_if_needed()

        # Auto-persist periodically (e.g., every 10 stores or if critical)
        if len(self._cache) % 10 == 0:
            self.save()

    def _record_hit(self, key: str):
        """Update hit stats and LRU."""
        entry = self._cache[key]
        entry.hit_count += 1
        entry.last_accessed = time.time()
        self._cache.move_to_end(key)
        self.hits += 1
        logger.debug("SemanticCache HIT key=%s", key[:8])

    def save(self):
        """Persist cache to disk."""
        try:
            # Save data
            data = {
                "entries": {k: asdict(v) for k, v in self._cache.items()},
                "next_id": self.next_id,
                "id_to_key": {str(k): v for k, v in self.id_to_key.items()},
            }
            with open(self.data_path, "w") as f:
                json.dump(data, f)

            # Save Faiss index
            if self.use_faiss and self.index and faiss:
                faiss.write_index(self.index, self.index_path)

            logger.info("Persisted SemanticCache to %s", self.persist_dir)
        except Exception as e:
            logger.warning("Failed to save SemanticCache: %s", e)

    def _load(self):
        """Load cache from disk."""
        if not os.path.exists(self.data_path):
            return

        try:
            # Load data
            with open(self.data_path, "r") as f:
                data = json.load(f)

            for k, v in data.get("entries", {}).items():
                self._cache[k] = CacheEntry(**v)

            self.next_id = data.get("next_id", 0)
            # JSON keys are always strings, convert back to int for ID map
            self.id_to_key = {int(k): v for k, v in data.get("id_to_key", {}).items()}

            # Load Faiss index
            if self.use_faiss and faiss and os.path.exists(self.index_path):
                self.index = faiss.read_index(self.index_path)
                logger.info("Loaded SemanticCache with %d entries", self.index.ntotal)
            else:
                # Rebuild index if missing
                logger.info("Rebuilding Faiss index from data...")
                self._rebuild_index()

        except Exception as e:
            logger.warning("Failed to load SemanticCache: %s", e)
            # Reset on failure
            self._cache.clear()
            self.id_to_key.clear()
            self.next_id = 0
            if self.use_faiss:
                self._init_faiss_index()

    def _rebuild_index(self):
        """Rebuild Faiss index from cached data."""
        if not self.use_faiss or not self.index:
            return

        self._init_faiss_index()
        self.id_to_key.clear()
        self.next_id = 0

        # Sort by creation time to maintain approximate ID order
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].created_at)

        if not sorted_entries:
            return

        embeddings = []
        keys = []

        for k, entry in sorted_entries:
            embeddings.append(entry.embedding)
            keys.append(k)

        if embeddings:
            emb_matrix = np.array(embeddings, dtype=np.float32)
            self.index.add(emb_matrix)
            for i, k in enumerate(keys):
                self.id_to_key[i] = k
            self.next_id = len(keys)

    def _query_to_text(self, query: MemoryQuery) -> str:
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
        now = time.time()
        # Remove expired
        expired = [
            k for k, v in self._cache.items() if now - v.created_at > v.ttl_seconds
        ]
        for key in expired:
            del self._cache[key]
            # Note: Removing from Faiss is hard/slow, we just ignore stale IDs on lookup

        # LRU Eviction
        while len(self._cache) > self.max_entries:
            key, _ = self._cache.popitem(last=False)
            # Again, Faiss index grows indefinitely until rebuild, but data stays bounded
