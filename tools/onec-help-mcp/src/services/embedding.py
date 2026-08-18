"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Сервис для работы с 1c-embeddings-service (BM25 корпус и векторизация)
"""

import asyncio
import json
import logging
import threading

# Настраиваем логирование для HTTP клиентов ДО импорта
# httpx - HTTP клиент (используется для запросов к embedding service)
logging.getLogger("httpx").setLevel(logging.WARNING)
# httpcore - низкоуровневый HTTP клиент (используется httpx)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
logging.getLogger("httpcore.connection").setLevel(logging.WARNING)

import httpx
from typing import List, Dict, Any, Optional
from ..config.settings import EMBEDDING_SERVICE_URL, EMBEDDING_REQUEST_TIMEOUT, EMBEDDING_BATCH_TIMEOUT

# Базовый образ: httpx==0.28.1 — базовый класс исключений запроса: RequestError (не RequestException)
logger = logging.getLogger(__name__)


class EmbeddingService:
    """Клиент для работы с 1c-embeddings-service"""
    
    def __init__(self):
        self.embedding_url = EMBEDDING_SERVICE_URL
    
    async def build_bm25_corpus(self, corpus: List[str], collection_name: str) -> bool:
        """
        Строит BM25 корпус через 1c-embeddings-service для конкретной коллекции
        
        Args:
            corpus: Список текстов для построения корпуса
            collection_name: Имя коллекции (обязательно для изоляции версий)
            
        Returns:
            True если корпус успешно построен, False иначе
        """
        try:
            if not corpus:
                logger.warning("⚠️ Пустой корпус, пропускаем построение BM25")
                return True
            
            if not collection_name:
                logger.error("❌ collection_name обязателен для построения BM25 корпуса")
                return False
            
            logger.info(f"🏗️ Построение BM25 корпуса для коллекции '{collection_name}' с {len(corpus)} документами")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.embedding_url}/bm25/build-corpus",
                    json={
                        "corpus": corpus,
                        "collection_name": collection_name
                    },
                    timeout=600.0  # Увеличенный таймаут для построения корпуса
                )
                response.raise_for_status()
                logger.info(f"✅ BM25 корпус успешно построен для коллекции '{collection_name}'")
                return True
                
        except httpx.ConnectError as e:
            logger.error(f"❌ Не удалось подключиться к 1c-embeddings-service: {e}")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP ошибка при построении BM25 корпуса: {e.response.status_code} - {e.response.text}")
            return False
        except httpx.TimeoutException as e:
            logger.error(f"❌ Таймаут при построении BM25 корпуса (600s): {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка при построении BM25 корпуса: {type(e).__name__}: {e}")
            return False
    
    async def get_dense_embedding(self, text: str) -> Optional[List[float]]:
        """
        Получает dense эмбеддинг для текста

        Args:
            text: Текст для векторизации

        Returns:
            Вектор эмбеддинга или None при ошибке
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.embedding_url}/embed",
                    json={
                        "texts": [text],
                        "task": "passage"
                    },
                    timeout=EMBEDDING_REQUEST_TIMEOUT
                )
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                return None
        except Exception as e:
            err_msg = str(e).strip() or repr(e) or type(e).__name__
            logger.error(f"❌ Ошибка получения dense эмбеддинга: {err_msg}", exc_info=True)
            return None

    async def get_dense_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Получает dense эмбеддинги для батча текстов одним запросом к /embed (batch).

        Args:
            texts: Список текстов для векторизации

        Returns:
            Список векторов эмбеддингов (None для текстов с ошибками)
        """
        if not texts:
            return []

        logger.debug(f"📊 Batch векторизация {len(texts)} текстов одним запросом")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.embedding_url}/embed",
                    json={"texts": texts, "task": "passage"},
                    timeout=EMBEDDING_BATCH_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                embeddings = data.get("embeddings")
                if embeddings and len(embeddings) == len(texts):
                    return embeddings
                if embeddings:
                    # Дополняем None если сервер вернул меньше
                    return list(embeddings) + [None] * (len(texts) - len(embeddings))
                return [None] * len(texts)
        except Exception as e:
            err_msg = str(e).strip() or repr(e) or type(e).__name__
            logger.error(f"❌ Ошибка получения batch dense эмбеддингов: {err_msg}", exc_info=True)
            raise
    
    async def get_sparse_embedding(self, text: str, collection_name: str) -> Dict[str, Any]:
        """
        Получает sparse эмбеддинг (BM25) для текста с учетом коллекции

        Args:
            text: Текст запроса
            collection_name: Имя коллекции для выбора правильного BM25 корпуса

        Returns:
            Sparse эмбеддинг в формате {"indices": [...], "values": [...]}
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.embedding_url}/embed/sparse",
                    json={
                        "texts": [text],
                        "collection_name": collection_name
                    },
                    timeout=EMBEDDING_REQUEST_TIMEOUT
                )

                if response.status_code != 200:
                    # Если корпус не построен (400) - возвращаем пустой вектор для fallback
                    if response.status_code == 400:
                        logger.warning(f"⚠️ BM25 корпус для коллекции '{collection_name}' не построен, используем dense-only поиск")
                        return {"indices": [], "values": []}
                    response.raise_for_status()

                data = response.json()
                embeddings = data.get("embeddings")

                if embeddings and len(embeddings) > 0:
                    sparse_result = embeddings[0]
                    if isinstance(sparse_result, dict) and "indices" in sparse_result and "values" in sparse_result:
                        return sparse_result

                # Fallback для альтернативных форматов
                if isinstance(data, dict) and "sparse_embeddings" in data:
                    se = data.get("sparse_embeddings")
                    if se and len(se) > 0:
                        sparse_result = se[0]
                        if isinstance(sparse_result, dict) and "indices" in sparse_result and "values" in sparse_result:
                            return sparse_result

                logger.warning(f"⚠️ Неожиданный формат sparse эмбеддинга, возвращаем пустой вектор")
                return {"indices": [], "values": []}

        except httpx.RequestError as e:
            logger.warning(f"⚠️ Ошибка получения sparse эмбеддинга: {e}, используем dense-only поиск")
            return {"indices": [], "values": []}
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при получении sparse эмбеддинга: {e}")
            return {"indices": [], "values": []}

    async def get_sparse_embeddings_batch(
        self,
        texts: List[str],
        collection_name: str
    ) -> List[Dict[str, Any]]:
        """
        Получает sparse эмбеддинги (BM25) для батча текстов через параллельные одиночные запросы

        Args:
            texts: Список текстов для векторизации
            collection_name: Имя коллекции для выбора правильного BM25 корпуса

        Returns:
            Список sparse эмбеддингов в формате [{"indices": [...], "values": [...]}, ...]
        """
        if not texts:
            return []

        logger.debug(f"📊 Параллельная sparse векторизация {len(texts)} текстов через {len(texts)} запросов")

        # Создаем задачи для параллельной векторизации
        tasks = [self.get_sparse_embedding(text, collection_name) for text in texts]

        # Выполняем все запросы параллельно
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return results


# Глобальный экземпляр сервиса
_embedding_service: Optional[EmbeddingService] = None
_embedding_service_lock = threading.Lock()


def get_embedding_service() -> EmbeddingService:
    """Получает глобальный экземпляр EmbeddingService (потокобезопасно)"""
    global _embedding_service

    # Быстрая проверка без блокировки (оптимизация производительности)
    if _embedding_service is not None:
        return _embedding_service

    # Блокировка только при инициализации
    with _embedding_service_lock:
        # Повторная проверка после получения блокировки (double-check locking)
        if _embedding_service is None:
            _embedding_service = EmbeddingService()
        return _embedding_service

