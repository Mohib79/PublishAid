import logging
import time
from typing import Optional, Protocol

from app.core.config import settings
from app.core.embeddings_config import EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


class EmbedderProtocol(Protocol):
    def embed_query(self, text: str) -> list[float]: ...


class SpecterEmbedder:
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

        self._model = SentenceTransformer(self.model_name, device=self.device)
        # Handle both get_embedding_dimension and older get_sentence_embedding_dimension
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
        _ = self._model.encode("warm-up text for model initialization", show_progress_bar=False)
        warmup_time = time.perf_counter() - warmup_start

        load_time = time.perf_counter() - start_time
        self._is_loaded = True
        logger.info(
            f"Embedding model loaded successfully in {load_time:.2f}s (warmup encode: {warmup_time:.2f}s, dim: {dim})"
        )

    def embed_query(self, text: str) -> list[float]:
        if not self._is_loaded or self._model is None:
            self.load()

        start = time.perf_counter()
        embedding = self._model.encode(text, show_progress_bar=False)
        elapsed = time.perf_counter() - start
        logger.debug(f"Query encoded in {elapsed * 1000:.1f}ms (length: {len(text)} chars)")

        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)


# Module-level singleton
_embedder_instance: Optional[SpecterEmbedder] = None


def get_embedder() -> EmbedderProtocol:
    """Dependency provider for FastAPI. Can be overridden in tests via app.dependency_overrides."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = SpecterEmbedder()
    return _embedder_instance


def init_embedder() -> None:
    """Called during FastAPI lifespan startup to initialize and warm up model."""
    embedder = get_embedder()
    if isinstance(embedder, SpecterEmbedder):
        embedder.load()
