"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Сервис для работы с Qdrant векторной базой данных.

Синхронные методы QdrantClient блокируют event loop. Все вызовы из async-кода
идут через *_async методы, которые выполняют sync-операции в thread pool
(asyncio.to_thread), чтобы несколько клиентов могли обрабатываться одновременно.
"""

import asyncio
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple

# Настраиваем логирование для qdrant_client ДО импорта
# qdrant_client может логировать HTTP запросы, отключаем их в INFO режиме
logging.getLogger("qdrant_client").setLevel(logging.WARNING)
logging.getLogger("qdrant_client.http").setLevel(logging.WARNING)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue,
    SparseVector, NamedVector, NamedSparseVector, ScoredPoint
)
from ..config.settings import QDRANT_URL, QDRANT_REQUEST_TIMEOUT, SPARSE_VECTOR_NAME

# Нативный гибридный поиск (qdrant-client 1.16+): Prefetch + FusionQuery RRF
try:
    from qdrant_client.models import Prefetch, FusionQuery, Fusion
    _NATIVE_HYBRID_AVAILABLE = True
except ImportError:
    Prefetch = FusionQuery = Fusion = None
    _NATIVE_HYBRID_AVAILABLE = False

logger = logging.getLogger(__name__)


class QdrantHelpService:
    """Клиент для работы с Qdrant для справки 1С"""
    
    def __init__(self):
        # Отключаем логирование HTTP запросов в qdrant_client
        # QdrantClient использует httpx внутри, но может иметь свой логгер
        import os
        # Отключаем логирование через переменную окружения, если поддерживается
        os.environ.setdefault("QDRANT_CLIENT_LOG_LEVEL", "WARNING")
        
        # check_compatibility=False: qdrant-client 1.16.x совместим с сервером 1.16.3
        self.client = QdrantClient(
            url=QDRANT_URL,
            timeout=QDRANT_REQUEST_TIMEOUT,
            check_compatibility=False
        )
        logger.info(f"✅ Qdrant клиент инициализирован: {QDRANT_URL}")
    
    def collection_exists(self, collection_name: str) -> bool:
        """
        Проверяет существование коллекции в Qdrant
        
        Args:
            collection_name: Имя коллекции
            
        Returns:
            True если коллекция существует, False иначе
        """
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            return collection_name in collection_names
        except Exception as e:
            logger.error(f"❌ Ошибка проверки существования коллекции '{collection_name}': {e}")
            return False
    
    def ensure_collection_exists(self, collection_name: str, vector_size: int = 384) -> bool:
        """
        Создает коллекцию в Qdrant если её нет.
        Размерность 384 соответствует intfloat/multilingual-e5-small (embedding-service-lite).
        
        Args:
            collection_name: Имя коллекции
            vector_size: Размер dense вектора (по умолчанию 384)
            
        Returns:
            True если коллекция существует или создана, False при ошибке
        """
        try:
            if self.collection_exists(collection_name):
                # Проверяем размерность: если не совпадает — пересоздаём коллекцию
                try:
                    info = self.client.get_collection(collection_name=collection_name)
                    if hasattr(info, "result"):
                        info = info.result
                    params = getattr(getattr(info, "config", None), "params", None)
                    vectors = getattr(params, "vectors", None) or getattr(params, "vectors_config", None)
                    if vectors:
                        content_params = vectors.get("content") if isinstance(vectors, dict) else None
                        existing_size = getattr(content_params, "size", None) if content_params else None
                        if existing_size is not None and existing_size != vector_size:
                            logger.warning(
                                f"⚠️ Коллекция '{collection_name}' имеет size={existing_size}, "
                                f"требуется {vector_size}. Пересоздаём коллекцию."
                            )
                            self.client.delete_collection(collection_name=collection_name)
                        else:
                            logger.debug(f"Коллекция '{collection_name}' уже существует")
                            return True
                    else:
                        logger.debug(f"Коллекция '{collection_name}' уже существует")
                        return True
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось проверить конфиг коллекции '{collection_name}': {e}")
                    return True
            
            logger.info(f"📦 Создание коллекции '{collection_name}' в Qdrant")
            
            # Создаем коллекцию с поддержкой dense и sparse векторов
            # Используем правильную структуру: vectors для dense, sparse_vectors для sparse
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "content": VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: {}
                }
            )
            
            logger.info(f"✅ Коллекция '{collection_name}' успешно создана")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания коллекции '{collection_name}': {e}")
            return False
    
    def upsert_points(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        """
        Сохраняет точки в коллекцию Qdrant
        
        Args:
            collection_name: Имя коллекции
            points: Список точек для сохранения
                Каждая точка должна содержать:
                - id: ID точки
                - vector: Dense вектор (опционально)
                - sparse_vector: Sparse вектор BM25 (опционально)
                - payload: Метаданные
            
        Returns:
            True если точки успешно сохранены, False при ошибке
        """
        try:
            if not points:
                logger.warning("⚠️ Нет точек для сохранения")
                return True
            
            # Преобразуем точки в формат Qdrant
            qdrant_points = []
            for point in points:
                point_id = point.get('id')
                payload = point.get('payload', {})
                
                # Формируем векторы
                vectors = {}
                
                # Dense вектор
                if 'vector' in point and point['vector']:
                    vectors['content'] = point['vector']
                
                # Sparse вектор BM25
                if 'sparse_vector' in point and point['sparse_vector']:
                    sparse = point['sparse_vector']
                    if isinstance(sparse, dict) and 'indices' in sparse and 'values' in sparse:
                        vectors[SPARSE_VECTOR_NAME] = SparseVector(
                            indices=sparse['indices'],
                            values=sparse['values']
                        )
                
                qdrant_point = PointStruct(
                    id=point_id,
                    vector=vectors if vectors else None,
                    payload=payload
                )
                qdrant_points.append(qdrant_point)
            
            # Сохраняем точки
            # Временно отключаем логирование HTTP запросов для этого вызова
            # (qdrant_client использует httpx, который может логировать запросы)
            import logging
            httpx_logger = logging.getLogger("httpx")
            httpcore_logger = logging.getLogger("httpcore")
            old_httpx_level = httpx_logger.level
            old_httpcore_level = httpcore_logger.level
            httpx_logger.setLevel(logging.WARNING)
            httpcore_logger.setLevel(logging.WARNING)
            
            try:
                self.client.upsert(
                    collection_name=collection_name,
                    points=qdrant_points
                )
            finally:
                # Восстанавливаем уровень логирования (хотя он уже WARNING)
                httpx_logger.setLevel(old_httpx_level)
                httpcore_logger.setLevel(old_httpcore_level)
            
            logger.info(f"✅ Сохранено {len(qdrant_points)} точек в коллекцию '{collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения точек в коллекцию '{collection_name}': {e}")
            return False
    
    def search(
        self,
        collection_name: str,
        query_vector: Optional[List[float]] = None,
        sparse_vector: Optional[SparseVector] = None,
        limit: int = 5,
        filters: Optional[Filter] = None
    ) -> Tuple[List[ScoredPoint], List[ScoredPoint]]:
        """
        Выполняет поиск в коллекции Qdrant
        
        Args:
            collection_name: Имя коллекции
            query_vector: Dense вектор запроса
            sparse_vector: Sparse вектор запроса (BM25)
            limit: Максимальное количество результатов
            filters: Фильтры для поиска
            
        Returns:
            Кортеж (dense_results, sparse_results) - списки найденных точек
        """
        try:
            # Гибридный поиск (dense + sparse)
            if query_vector and sparse_vector and sparse_vector.indices:
                # Sparse часть: используем SparseVector + using для sparse-индекса
                try:
                    sparse_result = self.client.query_points(
                        collection_name=collection_name,
                        query=sparse_vector,
                        using=SPARSE_VECTOR_NAME,
                        limit=limit,
                        query_filter=filters,
                    )
                    sparse_results = (
                        sparse_result.points
                        if hasattr(sparse_result, "points")
                        else list(sparse_result)
                    )
                except Exception as sparse_error:
                    logger.warning(f"⚠️ Ошибка sparse поиска: {sparse_error}, используем dense-only")
                    sparse_results = []

                # Dense часть
                dense_results = self._dense_search(collection_name, query_vector, limit, filters)

                return dense_results, sparse_results

            # Dense-only поиск
            elif query_vector:
                return self._dense_search(collection_name, query_vector, limit, filters), []

            # Sparse-only поиск
            elif sparse_vector and sparse_vector.indices:
                sparse_result = self.client.query_points(
                    collection_name=collection_name,
                    query=sparse_vector,
                    using=SPARSE_VECTOR_NAME,
                    limit=limit,
                    query_filter=filters,
                )
                sparse_results = (
                    sparse_result.points
                    if hasattr(sparse_result, "points")
                    else list(sparse_result)
                )
                return [], sparse_results

            else:
                logger.warning("⚠️ Не указан ни dense, ни sparse вектор для поиска")
                return [], []

        except Exception as e:
            logger.error(f"❌ Ошибка поиска в коллекции '{collection_name}': {e}")
            return [], []
    
    def _dense_search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int,
        filters: Optional[Filter]
    ) -> List[ScoredPoint]:
        """Выполняет dense-only поиск через query_points"""
        result = self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using="content",
            limit=limit,
            query_filter=filters,
        )
        return result.points if hasattr(result, "points") else list(result)

    def hybrid_search(
        self,
        collection_name: str,
        query_vector: List[float],
        sparse_vector: SparseVector,
        limit: int = 5,
        filters: Optional[Filter] = None,
        sparse_boost: float = 1.0
    ) -> List[ScoredPoint]:
        """
        Гибридный поиск (dense + sparse) с RRF.
        При qdrant-client 1.16+ — нативный query_points(prefetch, FusionQuery RRF).
        Иначе — два запроса + локальный RRF.
        """
        if _NATIVE_HYBRID_AVAILABLE and sparse_vector and sparse_vector.indices:
            try:
                sparse_query = SparseVector(
                    indices=sparse_vector.indices,
                    values=[v * sparse_boost for v in sparse_vector.values]
                )
                result = self.client.query_points(
                    collection_name=collection_name,
                    prefetch=[
                        Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=limit),
                        Prefetch(query=query_vector, using="content", limit=limit),
                    ],
                    query=FusionQuery(fusion=Fusion.RRF),
                    limit=limit,
                    query_filter=filters,
                )
                return result.points if hasattr(result, "points") else list(result)
            except Exception as e:
                logger.warning(f"⚠️ Нативный гибридный поиск не удался: {e}, fallback на два запроса + RRF")
        try:
            dense_results, sparse_results = self.search(
                collection_name=collection_name,
                query_vector=query_vector,
                sparse_vector=sparse_vector,
                limit=limit,
                filters=filters
            )
            if not sparse_results and not dense_results:
                return []
            if not sparse_results:
                return dense_results[:limit]
            if not dense_results:
                return sparse_results[:limit]
            return self._rrf_fuse(sparse_results, dense_results, k=60, sparse_boost=sparse_boost)[:limit]
        except Exception as e:
            logger.error(f"❌ Ошибка гибридного поиска в коллекции '{collection_name}': {e}")
            return []

    def _rrf_fuse(
        self,
        sparse_results: List[ScoredPoint],
        dense_results: List[ScoredPoint],
        k: int = 60,
        sparse_boost: float = 1.0
    ) -> List[ScoredPoint]:
        """Reciprocal Rank Fusion: объединяет sparse и dense результаты."""
        from collections import defaultdict
        scores: Dict[Any, float] = defaultdict(float)
        payloads: Dict[Any, ScoredPoint] = {}
        for rank, point in enumerate(sparse_results):
            rrf = sparse_boost / (k + rank + 1)
            scores[point.id] += rrf
            payloads[point.id] = point
        for rank, point in enumerate(dense_results):
            rrf = 1.0 / (k + rank + 1)
            scores[point.id] += rrf
            if point.id not in payloads:
                payloads[point.id] = point
        sorted_ids = sorted(scores.keys(), key=lambda i: scores[i], reverse=True)
        out = []
        for point_id in sorted_ids:
            p = payloads[point_id]
            out.append(ScoredPoint(id=p.id, score=scores[point_id], payload=p.payload, version=getattr(p, 'version', 0)))
        return out
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Удаляет коллекцию из Qdrant
        
        Args:
            collection_name: Имя коллекции
            
        Returns:
            True если коллекция удалена, False при ошибке
        """
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"✅ Коллекция '{collection_name}' удалена")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления коллекции '{collection_name}': {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о коллекции
        
        Args:
            collection_name: Имя коллекции
            
        Returns:
            Информация о коллекции или None при ошибке
        """
        try:
            collection_info = self.client.get_collection(collection_name=collection_name)
            # qdrant-client 1.16+: vectors_count removed, use points_count (same for single-vector collections)
            points_count = getattr(collection_info, "points_count", None) or getattr(
                collection_info, "vectors_count", 0
            )
            return {
                "name": collection_name,
                "points_count": points_count,
                "vectors_count": points_count,
                "status": getattr(collection_info, "status", None),
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации о коллекции '{collection_name}': {e}")
            return None

    # --- Async wrappers (run sync I/O in thread pool to not block event loop) ---

    async def collection_exists_async(self, collection_name: str) -> bool:
        return await asyncio.to_thread(self.collection_exists, collection_name)

    async def ensure_collection_exists_async(self, collection_name: str, vector_size: int = 384) -> bool:
        return await asyncio.to_thread(self.ensure_collection_exists, collection_name, vector_size)

    async def upsert_points_async(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        return await asyncio.to_thread(self.upsert_points, collection_name, points)

    async def search_async(
        self,
        collection_name: str,
        query_vector: Optional[List[float]] = None,
        sparse_vector: Optional[SparseVector] = None,
        limit: int = 5,
        filters: Optional[Filter] = None
    ) -> Tuple[List[ScoredPoint], List[ScoredPoint]]:
        return await asyncio.to_thread(
            self.search,
            collection_name,
            query_vector,
            sparse_vector,
            limit,
            filters
        )

    async def delete_collection_async(self, collection_name: str) -> bool:
        return await asyncio.to_thread(self.delete_collection, collection_name)

    async def get_collection_info_async(self, collection_name: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self.get_collection_info, collection_name)

    async def scroll_async(
        self,
        collection_name: str,
        scroll_filter: Optional[Filter] = None,
        limit: int = 100,
        with_payload: bool = True,
        with_vectors: bool = False
    ) -> list:
        """Scroll по коллекции. Возвращает список точек (первый элемент ответа client.scroll)."""
        result = await asyncio.to_thread(
            lambda: self.client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=limit,
                with_payload=with_payload,
                with_vectors=with_vectors
            )
        )
        return result[0] if result else []

    async def get_collections_async(self):
        """Список коллекций Qdrant (для health check и т.п.)."""
        return await asyncio.to_thread(self.client.get_collections)

    async def hybrid_search_async(
        self,
        collection_name: str,
        query_vector: List[float],
        sparse_vector: SparseVector,
        limit: int = 5,
        filters: Optional[Filter] = None,
        sparse_boost: float = 1.0
    ) -> List[ScoredPoint]:
        """Async обертка для гибридного поиска с встроенным RRF"""
        return await asyncio.to_thread(
            self.hybrid_search,
            collection_name,
            query_vector,
            sparse_vector,
            limit,
            filters,
            sparse_boost
        )


# Глобальный экземпляр сервиса
_qdrant_service: Optional[QdrantHelpService] = None
_qdrant_service_lock = threading.Lock()


def get_qdrant_service() -> QdrantHelpService:
    """Получает глобальный экземпляр QdrantHelpService (потокобезопасно)"""
    global _qdrant_service

    # Быстрая проверка без блокировки (оптимизация производительности)
    if _qdrant_service is not None:
        return _qdrant_service

    # Блокировка только при инициализации
    with _qdrant_service_lock:
        # Повторная проверка после получения блокировки (double-check locking)
        if _qdrant_service is None:
            _qdrant_service = QdrantHelpService()
        return _qdrant_service

