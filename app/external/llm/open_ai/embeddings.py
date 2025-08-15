import logging
import os
from typing import List

from openai import OpenAI
import hashlib
import math


logger = logging.getLogger(__name__)


class EmbeddingsClient:
    """Thin wrapper around OpenAI embeddings API.

    Uses text-embedding-3-small (1536 dims) by default.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        batch_size = int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "64"))
        out: List[List[float]] = []
        try:
            for i in range(0, len(texts), batch_size):
                chunk = texts[i:i + batch_size]
                response = self.client.embeddings.create(model=self.model, input=chunk)
                out.extend([d.embedding for d in response.data])
            if len(out) != len(texts):
                logger.warning("Embeddings count mismatch: %s texts vs %s vectors", len(texts), len(out))
            return out
        except Exception as e:
            if os.getenv("SEMANTIC_EMBEDDINGS_FALLBACK", "false").lower() in ("1", "true", "yes", "on"):
                logger.warning("Embedding API failed (%s). Using deterministic fallback embeddings for smoke test.", str(e))
                return [self._fallback_vector(t) for t in texts]
            raise

    @staticmethod
    def _fallback_vector(text: str, dim: int = 1536) -> List[float]:
        # Deterministic pseudo-embedding from SHA256; repeat digest to fill dims
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vals: List[float] = []
        i = 0
        while len(vals) < dim:
            b = h[i % len(h)]
            # map byte 0..255 to -0.5..0.5
            vals.append((b / 255.0) - 0.5)
            i += 1
        # L2 normalize
        norm = math.sqrt(sum(v*v for v in vals)) or 1.0
        return [v / norm for v in vals]


