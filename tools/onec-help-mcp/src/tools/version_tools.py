"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tools для работы с версиями платформы
"""

import asyncio
import logging
from typing import List
from ..config.version import (
    get_available_versions,
    is_version_available,
    get_collection_name,
    normalize_version,
)
from ..services.qdrant import get_qdrant_service

logger = logging.getLogger(__name__)


async def list_platform_versions(show_indexed_only: bool = False) -> str:
    """
    Получает список доступных версий платформы 1С с информацией об индексации
    
    Args:
        show_indexed_only: Если True, показывает только проиндексированные версии.
                          Если False, показывает все доступные версии с их статусом.
    
    Returns:
        Список версий с информацией о коллекциях Qdrant и статусе индексации
    """
    try:
        versions = await asyncio.to_thread(get_available_versions)
        
        if not versions:
            return "❌ Не найдено доступных версий платформы. Убедитесь, что файлы справки находятся в папке data/help1c/{version}/"
        
        qdrant_service = get_qdrant_service()
        
        if show_indexed_only:
            output = [f"📚 Проиндексированные версии платформы 1С:\n"]
            output.append(f"Всего доступно версий: {len(versions)}\n")
            
            indexed_count = 0
            not_indexed = []
            
            for version in versions:
                collection_name = get_collection_name(version)
                collection_info = await qdrant_service.get_collection_info_async(collection_name)
                
                if collection_info:
                    indexed_count += 1
                    output.append(f"✅ **{version}** - проиндексирована")
                    output.append(f"   📦 Коллекция: `{collection_name}`")
                    output.append(f"   📊 Точки: {collection_info['points_count']}")
                    output.append(f"   📊 Векторы: {collection_info['vectors_count']}")
                    output.append(f"   📈 Статус: {collection_info['status']}")
                    output.append("")
                else:
                    not_indexed.append(version)
            
            # Итоговая статистика
            output.append("---")
            output.append(f"📊 Итого:")
            output.append(f"   ✅ Проиндексировано: {indexed_count}/{len(versions)}")
            if not_indexed:
                output.append(f"   ❌ Требуют индексации: {len(not_indexed)}")
                output.append(f"   📋 Версии: {', '.join(not_indexed)}")
        else:
            output = [f"✅ Найдено {len(versions)} версий платформы 1С:\n"]
            
            for version in versions:
                collection_name = get_collection_name(version)
                collection_info = await qdrant_service.get_collection_info_async(collection_name)
                
                output.append(f"\n📦 **{version}**")
                output.append(f"   Коллекция Qdrant: `{collection_name}`")
                
                if collection_info:
                    output.append(f"   ✅ Точки в коллекции: {collection_info['points_count']}")
                    output.append(f"   📊 Векторы: {collection_info['vectors_count']}")
                    output.append(f"   📈 Статус: {collection_info['status']}")
                else:
                    output.append(f"   ⚠️ Коллекция не найдена в Qdrant (требуется индексация)")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка версий: {e}")
        return f"❌ Ошибка получения списка версий: {str(e)}"


async def get_platform_version_info(version: str) -> str:
    """
    Получает информацию о конкретной версии платформы
    
    Показывает:
    - Доступность файлов справки
    - Статус индексации (есть ли коллекция в Qdrant)
    - Статистику коллекции (количество точек, векторов)
    
    Args:
        version: Версия платформы (например, "8.3.24")
        
    Returns:
        Информация о версии с деталями индексации
    """
    try:
        normalized_version = normalize_version(version)
        
        if not is_version_available(normalized_version):
            available = await asyncio.to_thread(get_available_versions)
            if available:
                return f"❌ Версия '{normalized_version}' недоступна.\n\n" \
                       f"Доступные версии: {', '.join(available)}\n\n" \
                       f"Поместите файлы справки в папку: data/help1c/{normalized_version}/"
            else:
                return f"❌ Версия '{normalized_version}' недоступна.\n\n" \
                       f"Не найдено ни одной версии платформы в папке data/help1c/"
        
        collection_name = get_collection_name(normalized_version)
        qdrant_service = get_qdrant_service()
        collection_info = await qdrant_service.get_collection_info_async(collection_name)
        
        output = [f"📦 Информация о версии платформы **{normalized_version}**:\n"]
        output.append(f"   📁 Файлы справки: ✅ Доступны в data/help1c/{normalized_version}/")
        output.append(f"   📦 Коллекция Qdrant: `{collection_name}`")
        
        if collection_info:
            output.append(f"   ✅ Статус индексации: Проиндексирована")
            output.append(f"   📊 Точки в коллекции: {collection_info['points_count']}")
            output.append(f"   📊 Векторы в коллекции: {collection_info['vectors_count']}")
            output.append(f"   📈 Статус коллекции: {collection_info['status']}")
            output.append("")
            output.append("💡 Версия готова к использованию в search_1c_help()")
        else:
            output.append(f"   ❌ Статус индексации: Не проиндексирована")
            output.append("")
            output.append(f"💡 Для индексации используйте: index_platform_version('{normalized_version}')")
        
        return "\n".join(output)
        
    except ValueError as e:
        return f"❌ Неверный формат версии: {str(e)}\n\nИспользуйте формат: 8.3.24"
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о версии: {e}")
        return f"❌ Ошибка получения информации о версии: {str(e)}"

