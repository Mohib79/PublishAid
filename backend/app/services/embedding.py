"""Embedding service wrapper supporting asymmetric retrieval and long-text chunking."""

import logging
import time
from typing import Optional, Protocol

import numpy as np

from app.core.config import settings
from app.core.embeddings_config import EMBEDDING_DIMENSION, get_query_prefix

logger = logging.getLogger(__name__)


class EmbedderProtocol(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class JournalEmbedder:
    """SentenceTransformer embedding service with asymmetric query prefixing and sliding-window chunking."""

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.device = device or settings.EMBEDDING_DEVICE
        self._model = None
        self._is_loaded = False

    def load(self) -> None:
        if self._is_loaded:
            return

        start_time = time.perf_counter()
        logger.info(f"Loading embedding model '{self.model_name}' on device '{self.device}'...")

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Install requirements-embeddings.txt to use the embedding service."
            ) from e

        try:
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                local_files_only=True,
            )
        except Exception:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        # Prefer get_embedding_dimension() to avoid deprecation warnings in newer sentence-transformers
        if hasattr(self._model, "get_embedding_dimension"):
            dim = self._model.get_embedding_dimension()
        else:
            dim = self._model.get_sentence_embedding_dimension()

        if dim != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Model dimension {dim} does not match expected dimension {EMBEDDING_DIMENSION}"
            )

        # Warm-up encode
        warmup_start = time.perf_counter()
        _ = self._model.encode(
            "warm-up text for model initialization",
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        warmup_time = time.perf_counter() - warmup_start

        load_time = time.perf_counter() - start_time
        self._is_loaded = True
        logger.info(
            f"Embedding model loaded successfully in {load_time:.2f}s (warmup encode: {warmup_time:.2f}s, dim: {dim})"
        )

    def _encode_with_chunking(
        self,
        text: str,
        prefix: str = "",
        anchor_prefix: str = "",
    ) -> list[float]:
        """Encodes text, splitting long inputs into overlapping token windows when exceeding model limits."""
        if not self._is_loaded or self._model is None:
            self.load()

        clean_input = (text or "").strip()
        if not clean_input:
            return [0.0] * EMBEDDING_DIMENSION

        tokenizer = getattr(self._model, "tokenizer", None)
        max_model_tokens = min(int(getattr(self._model, "max_seq_length", 512) or 512), 512)

        if tokenizer is None:
            vec = np.asarray(
                self._model.encode(
                    f"{prefix}{clean_input}",
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ),
                dtype=np.float64,
            )
            norm = float(np.linalg.norm(vec))
            if norm > 1e-12:
                vec = vec / norm
            return vec.tolist()

        prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False) if prefix else []
        anchor_tokens = tokenizer.encode(anchor_prefix, add_special_tokens=False) if anchor_prefix else []
        token_ids = tokenizer.encode(clean_input, add_special_tokens=False)

        single_pass_limit = max(32, max_model_tokens - 16 - len(prefix_tokens))
        if len(token_ids) <= single_pass_limit:
            vec = np.asarray(
                self._model.encode(
                    f"{prefix}{clean_input}",
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ),
                dtype=np.float64,
            )
            norm = float(np.linalg.norm(vec))
            if norm > 1e-12:
                vec = vec / norm
            return vec.tolist()

        effective_chunk_limit = max(32, max_model_tokens - 16 - len(prefix_tokens) - len(anchor_tokens))
        chunk_size = min(settings.EMBEDDING_CHUNK_TOKENS, effective_chunk_limit)
        stride = max(1, chunk_size - settings.EMBEDDING_CHUNK_OVERLAP)

        chunks: list[str] = []
        for start_idx in range(0, len(token_ids), stride):
            window_ids = token_ids[start_idx : start_idx + chunk_size]
            chunk_body = tokenizer.decode(window_ids, skip_special_tokens=True).strip()
            if chunk_body:
                if start_idx > 0 and anchor_prefix:
                    chunks.append(f"{prefix}{anchor_prefix}{chunk_body}")
                else:
                    chunks.append(f"{prefix}{chunk_body}")
            if start_idx + chunk_size >= len(token_ids):
                break

        if not chunks:
            chunks = [f"{prefix}{clean_input}"]

        chunk_vecs = np.asarray(
            self._model.encode(chunks, normalize_embeddings=True, show_progress_bar=False),
            dtype=np.float64,
        )
        if chunk_vecs.ndim == 1:
            pooled = chunk_vecs
        else:
            pooled = chunk_vecs.mean(axis=0)

        norm = float(np.linalg.norm(pooled))
        if norm > 1e-12:
            pooled = pooled / norm
        return pooled.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Encodes a manuscript query using the asymmetric retrieval query instruction prefix."""
        start = time.perf_counter()
        prefix = get_query_prefix(self.model_name)
        embedding = self._encode_with_chunking(text, prefix=prefix)
        elapsed = time.perf_counter() - start
        logger.debug(f"Query encoded in {elapsed * 1000:.1f}ms (length: {len(text)} chars)")
        return embedding

    def embed_document(self, text: str, title: Optional[str] = None) -> list[float]:
        """Encodes a journal scope document without query prefix, anchoring title on overflow chunks."""
        start = time.perf_counter()
        anchor = f"{title.strip()}. " if title and title.strip() else ""
        embedding = self._encode_with_chunking(text, prefix="", anchor_prefix=anchor)
        elapsed = time.perf_counter() - start
        logger.debug(f"Document encoded in {elapsed * 1000:.1f}ms (length: {len(text)} chars)")
        return embedding


# Backwards-compatible alias
SpecterEmbedder = JournalEmbedder

# Module-level singleton
_embedder_instance: Optional[JournalEmbedder] = None


def get_embedder() -> EmbedderProtocol:
    """Dependency provider for FastAPI. Can be overridden in tests via app.dependency_overrides."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = JournalEmbedder()
    return _embedder_instance


def init_embedder() -> None:
    """Called during FastAPI lifespan startup to initialize and warm up model."""
    embedder = get_embedder()
    if isinstance(embedder, JournalEmbedder):
        embedder.load()
