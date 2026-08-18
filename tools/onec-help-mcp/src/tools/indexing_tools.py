"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tools для индексации справки 1С
"""

import asyncio
import logging
import threading
from typing import Optional, Dict
from ..core.indexer import HelpIndexer
from ..config.version import (
    get_available_versions,
    is_version_available,
    normalize_version,
    get_collection_name
)
from ..services.qdrant import get_qdrant_service
from ..utils.indexing_status import get_status

logger = logging.getLogger(__name__)

# Per-version блокировки для параллельной индексации разных версий
# Защита от двойного вызова (два MCP-клиента, двойной клик на одной версии)
_version_locks: Dict[str, asyncio.Lock] = {}
_version_locks_lock = threading.Lock()  # Для потокобезопасного создания locks


def _get_version_lock(version: str) -> asyncio.Lock:
    """Получает asyncio.Lock для конкретной версии (потокобезопасно)"""
    with _version_locks_lock:
        if version not in _version_locks:
            _version_locks[version] = asyncio.Lock()
        return _version_locks[version]


async def index_platform_version(version: str) -> str:
    """
    Индексирует справку для указанной версии платформы 1С
    
    Процесс индексации включает:
    1. Парсинг HBK файлов из папки data/help1c/{version}/
    2. Построение BM25 корпуса через 1c-embeddings-service
    3. Векторизацию текстов справки
    4. Сохранение векторов в Qdrant (коллекция 1c_help_{version})
    
    Индексация выполняется в фоновой asyncio-задаче, чтобы отмена
    клиентского MCP-запроса не прерывала длительный процесс.
    
    Args:
        version: Версия платформы для индексации (например, "8.3.24")
        
    Returns:
        Сообщение о запуске индексации в фоновом режиме
    """
    try:
        normalized_version = normalize_version(version)
    except ValueError as e:
        return f"❌ Неверный формат версии: {str(e)}\n\n" \
               f"Используйте формат: 8.3.24 (например, '8.3.24', '8.3.25')"

    busy = _check_indexing_busy(normalized_version)
    if busy:
        return busy

    task = asyncio.create_task(_run_index_in_background(normalized_version))
    task.add_done_callback(_log_index_background_result)

    return f"⏳ Индексация справки для версии **{normalized_version}** запущена в фоновом режиме.\n\n" \
           f"Отслеживайте прогресс в логах: docker logs -f onec-help-mcp"


async def _run_index_in_background(version: str) -> None:
    """
    Выполняет индексацию в фоновой задаче с защитой от повторного запуска.

    Args:
        version: Версия платформы (нормализованная)
    """
    # Получаем блокировку для конкретной версии
    version_lock = _get_version_lock(version)

    async with version_lock:
        # Повторная проверка после получения блокировки (на случай гонки)
        busy = _check_indexing_busy(version)
        if busy:
            logger.warning(busy)
            return
        await _index_platform_version_impl(version)


def _log_index_background_result(task: asyncio.Task) -> None:
    """
    Логирует результат фоновой индексации (успех или исключение).

    Args:
        task: Завершённая asyncio-задача индексации
    """
    if task.cancelled():
        logger.error(f"❌ Фоновая индексация отменена (version={task.get_name()})")
        return
    exc = task.exception()
    if exc is not None:
        logger.error(f"❌ Ошибка фоновой индексации: {type(exc).__name__}: {exc}")


async def _index_platform_version_impl(version: str) -> str:
    try:
        # Нормализуем версию
        normalized_version = normalize_version(version)
        
        # Проверяем доступность версии
        if not is_version_available(normalized_version):
            available = await asyncio.to_thread(get_available_versions)
            if available:
                return f"❌ Версия '{normalized_version}' недоступна.\n\n" \
                       f"Доступные версии: {', '.join(available)}\n\n" \
                       f"Убедитесь, что файлы справки находятся в папке: data/help1c/{normalized_version}/"
            else:
                return f"❌ Версия '{normalized_version}' недоступна.\n\n" \
                       f"Не найдено ни одной версии платформы в папке data/help1c/\n\n" \
                       f"Поместите файлы справки (.hbk, .res) в папку data/help1c/{normalized_version}/"
        
        logger.info(f"🚀 Начало индексации справки для версии {normalized_version}")
        
        # Создаем индексатор
        indexer = HelpIndexer(normalized_version)
        
        # Запускаем индексацию
        success = await indexer.index_version()
        
        if success:
            # Проверяем результат в Qdrant
            collection_name = get_collection_name(normalized_version)
            qdrant_service = get_qdrant_service()
            collection_info = await qdrant_service.get_collection_info_async(collection_name)
            
            if collection_info:
                output = [
                    f"✅ Индексация справки для версии **{normalized_version}** завершена успешно!\n",
                    f"📦 Коллекция Qdrant: `{collection_name}`",
                    f"📊 Точки в коллекции: {collection_info['points_count']}",
                    f"📊 Векторы в коллекции: {collection_info['vectors_count']}",
                    f"📈 Статус: {collection_info['status']}",
                    "",
                    "💡 Теперь вы можете использовать search_1c_help() для поиска в этой версии справки."
                ]
                return "\n".join(output)
            else:
                return f"⚠️ Индексация завершена, но коллекция '{collection_name}' не найдена в Qdrant. " \
                       f"Проверьте логи для деталей."
        else:
            return f"❌ Ошибка индексации справки для версии '{normalized_version}'. " \
                   f"Проверьте логи для деталей."
        
    except ValueError as e:
        return f"❌ Неверный формат версии: {str(e)}\n\n" \
               f"Используйте формат: 8.3.24 (например, '8.3.24', '8.3.25')"
    except Exception as e:
        logger.error(f"❌ Ошибка индексации версии {version}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка индексации: {str(e)}\n\nПроверьте логи для деталей."


def _check_indexing_busy(version: str) -> Optional[str]:
    """
    Проверяет, идет ли индексация для конкретной версии.

    Args:
        version: Версия платформы для проверки

    Returns:
        Сообщение об ошибке если индексация идет, иначе None
    """
    st = get_status(version)
    if st.get("status") in ("parsing", "building_bm25", "vectorizing"):
        v = st.get("version", "?")
        return f"⏳ Индексация уже выполняется (версия {v}). Дождитесь завершения или проверьте статус: GET /help/indexing/status"
    return None


async def get_indexed_platform_versions() -> str:
    """
    Получает список всех проиндексированных версий платформы
    
    Показывает:
    - Какие версии доступны в папке data/help1c/
    - Какие версии проиндексированы (есть коллекции в Qdrant)
    - Статистику по каждой проиндексированной версии
    
    Returns:
        Отформатированный список версий с статусом индексации
    """
    try:
        # Получаем все доступные версии (iterdir в thread)
        available_versions = await asyncio.to_thread(get_available_versions)
        
        if not available_versions:
            return "❌ Не найдено доступных версий платформы.\n\n" \
                   "Поместите файлы справки (.hbk, .res) в папки:\n" \
                   "- data/help1c/8.3.24/\n" \
                   "- data/help1c/8.3.25/\n" \
                   "и т.д."
        
        qdrant_service = get_qdrant_service()
        
        output = [f"📚 Статус индексации справки 1С:\n"]
        output.append(f"Всего доступно версий: {len(available_versions)}\n")
        
        indexed_count = 0
        not_indexed = []
        
        for version in available_versions:
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
                output.append(f"❌ **{version}** - не проиндексирована")
                output.append(f"   📦 Коллекция: `{collection_name}` (не найдена)")
                output.append(f"   💡 Используйте index_platform_version('{version}') для индексации")
                output.append("")
        
        # Итоговая статистика
        output.append("---")
        output.append(f"📊 Итого:")
        output.append(f"   ✅ Проиндексировано: {indexed_count}/{len(available_versions)}")
        if not_indexed:
            output.append(f"   ❌ Требуют индексации: {len(not_indexed)}")
            output.append(f"   📋 Версии: {', '.join(not_indexed)}")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка проиндексированных версий: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка получения списка версий: {str(e)}"


async def reindex_platform_version(version: str, force: bool = False) -> str:
    """
    Переиндексирует справку для указанной версии платформы
    
    Если коллекция уже существует, она будет перезаписана (при force=True)
    или будет показано предупреждение (при force=False).
    
    Args:
        version: Версия платформы для переиндексации
        force: Принудительная переиндексация (удаление существующей коллекции)
        
    Returns:
        Результат переиндексации
    """
    try:
        normalized_version = normalize_version(version)
        collection_name = get_collection_name(normalized_version)
        
        qdrant_service = get_qdrant_service()
        collection_info = await qdrant_service.get_collection_info_async(collection_name)
        
        if collection_info and not force:
            return f"⚠️ Версия '{normalized_version}' уже проиндексирована.\n\n" \
                   f"Коллекция `{collection_name}` содержит {collection_info['points_count']} точек.\n\n" \
                   f"Для принудительной переиндексации используйте:\n" \
                   f"reindex_platform_version('{normalized_version}', force=True)"
        
        # Если force=True и коллекция существует, удаляем её
        if collection_info and force:
            logger.info(f"🗑️ Удаление существующей коллекции '{collection_name}' для переиндексации")
            await qdrant_service.delete_collection_async(collection_name)
        
        # Запускаем индексацию в фоновом режиме
        return await index_platform_version(normalized_version)
        
    except ValueError as e:
        return f"❌ Неверный формат версии: {str(e)}"
    except Exception as e:
        logger.error(f"❌ Ошибка переиндексации версии {version}: {e}")
        return f"❌ Ошибка переиндексации: {str(e)}"

