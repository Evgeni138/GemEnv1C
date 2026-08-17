import asyncio
import logging
from typing import List

import torch
from sentence_transformers import SentenceTransformer

from .config import get_settings


logger = logging.getLogger(__name__)


class DenseEncoder:
    """
    Обёртка над SentenceTransformer с поддержкой CPU/GPU и batch-encode.
    Модель по умолчанию: intfloat/multilingual-e5-small (dim=384).
    """

    def __init__(self) -> None:
        settings = get_settings()

        self.model_name = settings.embedding_model_name
        self._device = self._resolve_device(settings.embedding_device)

        logger.info(
            f"Initializing DenseEncoder model='{self.model_name}' device='{self._device}'"
        )
        # trust_remote_code=False — стандартные sentence-transformers модели
        self.model = SentenceTransformer(self.model_name, device=self._device)

        try:
            dim = self.model.get_sentence_embedding_dimension()
        except Exception:  # pragma: no cover - защитный код
            dim = None
        self.dimension = dim

    @staticmethod
    def _resolve_device(device_cfg: str) -> str:
        device_cfg = device_cfg or "auto"
        if device_cfg == "cpu":
            return "cpu"
        if device_cfg == "gpu":
            # Явно просили GPU, но если нет CUDA — падаем обратно на CPU
            return "cuda" if torch.cuda.is_available() else "cpu"
        # auto
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    async def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Асинхронная обёртка над синхронным encode, чтобы не блокировать event loop.
        """

        if not texts:
            return []

        # SentenceTransformer.encode синхронный → выносим в отдельный поток
        embeddings = await asyncio.to_thread(
            self.model.encode,
            texts,
            batch_size=min(len(texts), 32),
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # Преобразуем в обычные Python-списки для сериализации в JSON
        return [vec.tolist() for vec in embeddings]

    def get_backend_info(self) -> dict:
        return {
            "model": self.model_name,
            "dimension": self.dimension,
            "device": self._device,
            "backend": "sentence-transformers",
        }

