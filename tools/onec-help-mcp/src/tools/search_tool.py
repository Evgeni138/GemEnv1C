"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tool для поиска в справке 1С
"""

import asyncio
import logging
from typing import Optional

from fastmcp.server.dependencies import get_http_headers

from ..config.version import get_platform_version, get_collection_name
from ..services.qdrant import get_qdrant_service
from ..core.search import search_help

logger = logging.getLogger(__name__)


async def search_1c_help(
    query: str,
    platform_version: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Поиск в справке 1С с поддержкой гибридного поиска (BM25 + семантический)
    
    Args:
        query: Поисковый запрос
        platform_version: Версия платформы (например, "8.3.24"). 
                          Если не указана, используется версия из заголовка x-platform-version 
                          или версия по умолчанию из конфигурации
        limit: Максимальное количество результатов (по умолчанию 10, можно увеличить)
        
    Returns:
        Отформатированные результаты поиска
    """
    try:
        # Получаем заголовки из FastMCP контекста
        headers = None
        try:
            headers = get_http_headers()
        except (AttributeError, RuntimeError, LookupError):
            # Если заголовки недоступны (не в контексте MCP запроса), используем None
            pass

        # Определяем фактическую версию и коллекцию
        version = await asyncio.to_thread(get_platform_version, headers=headers, tool_param=platform_version)
        collection_name = get_collection_name(version)
        qdrant_service = get_qdrant_service()

        # Если коллекции нет — возвращаем понятное сообщение вместо сырого 404
        if not await qdrant_service.collection_exists_async(collection_name):
            if platform_version:
                return (
                    f"❌ Для версии платформы {platform_version} справка не проиндексирована "
                    f"(коллекция '{collection_name}' отсутствует в Qdrant).\n"
                    f"💡 Сначала вызовите index_platform_version(version='{platform_version}'), "
                    f"либо уберите параметр platform_version, чтобы использовать версию по умолчанию."
                )
            else:
                return (
                    f"❌ Для версии платформы {version} справка не проиндексирована "
                    f"(коллекция '{collection_name}' отсутствует в Qdrant).\n"
                    f"💡 Сначала вызовите index_platform_version(version='{version}')."
                )
        
        results = await search_help(
            query=query,
            platform_version=platform_version,
            limit=limit,
            use_hybrid=True,
            headers=headers,
        )
        
        if not results:
            return f"❌ По запросу '{query}' ничего не найдено в справке 1С"
        
        # Проверяем, есть ли среди результатов API элементы
        has_api_elements = any(
            result.get('metadata', {}).get('element_type') in ['function', 'method', 'property', 'type', 'constructor']
            for result in results
        )
        
        # Форматируем результаты
        output = [
            f"✅ Показано до {limit} результатов по запросу '{query}' "
            f"(сейчас {len(results)}, параметр limit можно увеличить):\n"
        ]
        
        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. **{result['title']}** (релевантность: {result['score']:.3f})")
            output.append(f"   📄 Тип: {result['type']}")
            if result.get('description'):
                output.append(f"   📝 Описание: {result['description']}")
            if result.get('file_path'):
                output.append(f"   📁 Файл: {result['file_path']}")
            if result.get('platform_version'):
                output.append(f"   🔢 Версия платформы: {result['platform_version']}")
        
        # Добавляем подсказку для API элементов
        if has_api_elements:
            output.append(
                f"\n💡 Если вы искали API элемент (функцию, метод, свойство, тип), используйте:\n"
                f"   search_1c_platform_api(query='{query}') для более точного поиска по структурированным API элементам"
            )
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска в справке: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка поиска в справке: {str(e)}"

