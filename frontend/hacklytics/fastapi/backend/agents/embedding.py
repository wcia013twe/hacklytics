import time
from typing import Optional, Dict
from sentence_transformers import SentenceTransformer
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from contracts.models import EmbeddingResult

logger = logging.getLogger(__name__)

class EmbeddingAgent:
    """
    Converts text narratives to 384-dim semantic vectors using MiniLM-L6.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.warmup_complete = False

    async def warmup_model(self) -> Dict:
        """Task 4.2: Warmup model (first call is slow ~500ms)"""
        start = time.perf_counter()
        self.model = SentenceTransformer(self.model_name)
        # Warm up with dummy text
        _ = self.model.encode("warmup text")
        warmup_time = (time.perf_counter() - start) * 1000
        self.warmup_complete = True
        logger.info(f"Model warmed up in {warmup_time:.2f}ms")
        return {"warmup_complete": True, "warmup_time_ms": warmup_time}

    async def embed_text(self, text: str, request_id: str) -> EmbeddingResult:
        """
        Task 4.1: Embed text to 384-dim vector

        Returns:
            EmbeddingResult with vector, timing, metadata
        """
        if not self.model:
            await self.warmup_model()

        # Truncate to 200 chars if needed
        if len(text) > 200:
            logger.warning(f"Text exceeds 200 chars, truncating: {text[:50]}...")
            text = text[:200]

        # Handle empty text
        if not text.strip():
            logger.warning("Empty text provided, returning zero vector")
            return EmbeddingResult(
                request_id=request_id,
                vector=[0.0] * 384,
                embedding_time_ms=0.0,
                model=self.model_name
            )

        start = time.perf_counter()
        vector = self.model.encode(text).tolist()
        embed_time = (time.perf_counter() - start) * 1000

        return EmbeddingResult(
            request_id=request_id,
            vector=vector,
            embedding_time_ms=embed_time,
            model=self.model_name
        )
