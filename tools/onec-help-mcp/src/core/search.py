"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Модуль поиска в справке 1С с поддержкой гибридного поиска (BM25 + Dense)
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from qdrant_client.models import SparseVector

from ..config.version import get_collection_name, get_platform_version
from ..config.settings import SPARSE_BOOST, USE_HYBRID_SEARCH
from ..services.embedding import get_embedding_service
from ..services.qdrant import get_qdrant_service

logger = logging.getLogger(__name__)


async def search_help(
    query: str,
    platform_version: Optional[str] = None,
    headers: Optional[dict] = None,
    limit: int = 10,
    use_hybrid: bool = True
) -> List[Dict[str, Any]]:
    """
    Выполняет поиск в справке 1С с поддержкой гибридного поиска
    
    Args:
        query: Поисковый запрос
        platform_version: Версия платформы (опционально)
        headers: HTTP заголовки для определения версии
        limit: Максимальное количество результатов
        use_hybrid: Использовать гибридный поиск (BM25 + Dense)
        
    Returns:
        Список результатов поиска с релевантностью
    """
    try:
        # Определяем версию платформы (file I/O в thread)
        version = await asyncio.to_thread(get_platform_version, headers=headers, tool_param=platform_version)
        collection_name = get_collection_name(version)
        
        logger.info(f"🔍 Поиск в справке версии {version} (коллекция: {collection_name})")
        
        # Получаем сервисы
        embedding_service = get_embedding_service()
        qdrant_service = get_qdrant_service()
        
        # Получаем dense эмбеддинг запроса
        query_vector = await embedding_service.get_dense_embedding(query)
        if not query_vector:
            logger.error("❌ Не удалось получить dense эмбеддинг для запроса")
            return []
        
        # Гибридный поиск (BM25 + Dense) с встроенным RRF Qdrant
        if use_hybrid and USE_HYBRID_SEARCH:
            # Получаем sparse эмбеддинг (BM25)
            sparse_embedding_dict = await embedding_service.get_sparse_embedding(query, collection_name)

            sparse_vector = None
            if sparse_embedding_dict.get('indices') and sparse_embedding_dict.get('values'):
                sparse_vector = SparseVector(
                    indices=sparse_embedding_dict['indices'],
                    values=sparse_embedding_dict['values']
                )

            # Выполняем гибридный поиск с встроенным RRF
            if sparse_vector and sparse_vector.indices:
                logger.debug(f"🔀 Гибридный поиск (dense + sparse BM25) с встроенным RRF")
                search_results = await qdrant_service.hybrid_search_async(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    sparse_vector=sparse_vector,
                    limit=limit,
                    sparse_boost=SPARSE_BOOST
                )
            else:
                # Fallback на dense-only
                logger.debug("⚠️ Sparse вектор пустой, используем dense-only поиск")
                dense_results, _ = await qdrant_service.search_async(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    sparse_vector=None,
                    limit=limit
                )
                search_results = dense_results
        else:
            # Dense-only поиск
            logger.debug("📊 Dense-only поиск")
            dense_results, _ = await qdrant_service.search_async(
                collection_name=collection_name,
                query_vector=query_vector,
                sparse_vector=None,
                limit=limit
            )
            search_results = dense_results
        
        # Форматируем результаты
        results = []
        for result in search_results:
            payload = result.payload
            results.append({
                "score": result.score,
                "id": str(result.id),
                "title": payload.get("title", ""),
                "description": payload.get("text", "")[:200],  # Первые 200 символов
                "content": payload.get("content", ""),
                "type": payload.get("type", "unknown"),
                "file_path": payload.get("file_path", ""),
                "platform_version": payload.get("platform_version", version),
                "metadata": payload.get("metadata", {})
            })
        
        logger.info(f"✅ Найдено {len(results)} результатов по запросу '{query}'")
        return results
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска в справке: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

