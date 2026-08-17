"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Главный файл MCP сервера для справки 1С
Объединяет все компоненты: MCP tools, REST API routes, инициализацию
"""

import logging
import os

# Настраиваем логирование ДО импорта других модулей
# Устанавливаем уровень WARNING для шумных логгеров
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("starlette").setLevel(logging.WARNING)

# Отключаем access логи uvicorn через переменную окружения
# Это работает для FastMCP, который использует uvicorn внутри
if os.getenv("LOG_LEVEL", "INFO").upper() == "INFO":
    os.environ["UVICORN_ACCESS_LOG"] = "false"

from fastmcp import FastMCP
from starlette.responses import JSONResponse

# Импорты конфигурации
from .config.settings import SERVER_NAME, SERVER_HOST, SERVER_PORT, LOG_LEVEL

# Импорты для инициализации (чтобы модули загрузились)
from .services.qdrant import get_qdrant_service  # noqa: F401
from .services.embedding import get_embedding_service  # noqa: F401

# Импорты MCP Tools
from .tools.search_tool import search_1c_help
from .tools.platform_tools import (
    search_1c_platform_api,
    get_1c_platform_element,
    get_1c_platform_type_members,
)
from .tools.manage_help_tool import manage_platform_help

# Импорты REST API handlers
from .api.rest_handlers import (
    search_help_handler,
    search_platform_api_handler,
    get_element_handler,
    get_type_members_handler,
    manage_help_handler as manage_help_api_handler
)

# Фильтр для подавления HTTP Request логов в INFO режиме
class HTTPRequestFilter(logging.Filter):
    """Фильтр для подавления HTTP Request логов в INFO режиме"""
    def filter(self, record):
        # Блокируем логи с 'HTTP Request' в сообщении
        message = record.getMessage()
        if 'HTTP Request' in message:
            return False
        return True

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Логи из src.* не пропагируют в root — один вывод (избегаем дубля: root получает второй handler от uvicorn)
src_logger = logging.getLogger("src")
src_logger.propagate = False
src_logger.setLevel(getattr(logging, LOG_LEVEL.upper()))
if not src_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    if LOG_LEVEL.upper() == "INFO":
        _h.addFilter(HTTPRequestFilter())
    src_logger.addHandler(_h)

# Применяем фильтр для HTTP Request логов в INFO режиме (для root, если что-то логирует туда)
if LOG_LEVEL.upper() == "INFO":
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if not any(isinstance(f, HTTPRequestFilter) for f in handler.filters):
            handler.addFilter(HTTPRequestFilter())

# Устанавливаем уровень WARNING для шумных логгеров (они будут показываться только в DEBUG режиме)
# В режиме INFO эти логи не будут показываться, только в DEBUG
# httpx - HTTP клиент (используется для запросов к embedding service и qdrant)
logging.getLogger("httpx").setLevel(logging.WARNING)
# httpcore - низкоуровневый HTTP клиент
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpcore.http11").setLevel(logging.WARNING)
logging.getLogger("httpcore.connection").setLevel(logging.WARNING)
# uvicorn - ASGI сервер (настраиваем через переменные окружения тоже)
os.environ["UVICORN_LOG_LEVEL"] = "warning"
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
# starlette - веб-фреймворк
logging.getLogger("starlette").setLevel(logging.WARNING)

# Инициализация FastMCP
mcp = FastMCP(name=SERVER_NAME)

# Регистрация MCP Tools

# Основные инструменты поиска
mcp.tool()(search_1c_help)

# Объединённый admin-tool для версий/индексации
mcp.tool()(manage_platform_help)

# Инструменты для работы с API платформы
mcp.tool()(search_1c_platform_api)
mcp.tool()(get_1c_platform_element)
mcp.tool()(get_1c_platform_type_members)

# REST API routes


@mcp.custom_route("/", methods=["GET"])
async def root(request=None):
    """Корневой endpoint"""
    return JSONResponse({
        "service": SERVER_NAME,
        "status": "running",
        "version": "2.0.0",
        "protocols": {
            "mcp": "/mcp",
            "rest_api": "/api/*"
        },
        "endpoints": {
            "health": "GET /health",
            "search": "POST /api/search",
            "platform_search": "POST /api/platform/search",
            "platform_element": "POST /api/platform/element",
            "platform_type_members": "POST /api/platform/type-members",
            "manage": "POST /api/manage",
            "indexing_status": "GET /help/indexing/status"
        },
        "docs": "See TOOLS.md for REST API documentation"
    })


@mcp.custom_route("/help/indexing/status", methods=["GET"])
async def get_indexing_status(request=None):
    """Получить статус индексации справки"""
    try:
        from .tools.version_tools import list_platform_versions
        import asyncio
        from .config.version import get_available_versions
        from .services.qdrant import get_qdrant_service
        from .config.version import get_collection_name
        from .utils.indexing_status import get_status
        
        # Получаем все статусы индексации (словарь {version: status_dict})
        all_statuses = get_status()

        # Получаем список проиндексированных версий (iterdir в thread)
        qdrant_service = get_qdrant_service()
        available_versions = await asyncio.to_thread(get_available_versions)

        indexed_versions = []
        for version in available_versions:
            collection_name = get_collection_name(version)
            collection_info = await qdrant_service.get_collection_info_async(collection_name)
            if collection_info:
                indexed_versions.append({
                    "version": version,
                    "points_count": collection_info.get("points_count", 0),
                    "status": collection_info.get("status", "unknown")
                })

        # Ищем активные индексации и обновляем points_count из Qdrant
        active_indexing = []
        for version, status_dict in all_statuses.items():
            if status_dict["status"] in ["parsing", "building_bm25", "vectorizing"]:
                if status_dict.get("collection_name"):
                    try:
                        collection_info = await qdrant_service.get_collection_info_async(status_dict["collection_name"])
                        if collection_info:
                            status_dict["points_count"] = collection_info.get("points_count", 0)
                    except:
                        pass
                active_indexing.append(status_dict)

        # Формируем ответ
        # Если есть активная индексация, показываем первую (для обратной совместимости)
        # Также добавляем список всех активных индексаций
        if active_indexing:
            current_status = active_indexing[0]
        else:
            current_status = {
                "status": "idle",
                "version": None,
                "error_message": None,
                "total_items": 0,
                "processed_items": 0,
                "total_batches": 0,
                "current_batch": 0,
                "points_count": 0,
                "estimated_time_remaining": 0
            }

        response = {
            "status": current_status["status"],
            "version": current_status["version"],
            "indexed_versions": indexed_versions,
            "error_message": current_status.get("error_message"),
            # Детальная информация о текущей индексации
            "total_items": current_status.get("total_items", 0),
            "processed_items": current_status.get("processed_items", 0),
            "total_batches": current_status.get("total_batches", 0),
            "current_batch": current_status.get("current_batch", 0),
            "points_count": current_status.get("points_count", 0),
            "estimated_time_remaining": current_status.get("estimated_time_remaining", 0),
            # Новое поле: список всех активных индексаций
            "active_indexing": active_indexing
        }
        
        return JSONResponse(response)
    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/help/indexing/index", methods=["POST"])
async def start_indexing(request):
    """Запустить индексацию версии"""
    try:
        import json
        body = await request.body()
        data = json.loads(body)
        version = data.get("version")
        
        if not version:
            return JSONResponse({"error": "Version is required"}, status_code=400)
        
        from .tools.indexing_tools import index_platform_version
        # Индексация выполняется синхронно в этом handler
        result = await index_platform_version(version)
        
        return JSONResponse({
            "status": "accepted",
            "message": "Indexing started",
            "version": version
        })
    except Exception as e:
        logger.error(f"Ошибка запуска индексации: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/help/indexing/reindex", methods=["POST"])
async def start_reindexing(request):
    """Запустить переиндексацию версии"""
    try:
        import json
        body = await request.body()
        data = json.loads(body)
        version = data.get("version")
        
        if not version:
            return JSONResponse({"error": "Version is required"}, status_code=400)
        
        # Запускаем переиндексацию в фоне
        from .tools.indexing_tools import reindex_platform_version
        result = await reindex_platform_version(version, force=True)
        
        return JSONResponse({
            "status": "accepted",
            "message": "Reindexing started",
            "version": version
        })
    except Exception as e:
        logger.error(f"Ошибка запуска переиндексации: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request=None):
    """Проверка работоспособности сервиса"""
    try:
        # Проверяем подключение к Qdrant
        qdrant_service = get_qdrant_service()
        try:
            await qdrant_service.get_collections_async()
            qdrant_status = "OK"
        except Exception as e:
            logger.warning(f"Qdrant health check failed: {e}")
            qdrant_status = f"ERROR: {str(e)}"

        # Проверяем подключение к 1c-embeddings-service
        embedding_service = get_embedding_service()
        embedding_status = "OK"  # Проверка будет при первом запросе

        # Проверяем доступные версии (iterdir в thread)
        import asyncio
        from .config.version import get_available_versions
        available_versions = await asyncio.to_thread(get_available_versions)

        return JSONResponse({
            "status": "healthy",
            "service": SERVER_NAME,
            "version": "2.0.0",
            "qdrant": qdrant_status,
            "embedding_service": embedding_status,
            "available_versions": len(available_versions),
            "versions": available_versions[:5] if available_versions else []  # Первые 5 версий
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status_code=500)


# ============================================================================
# REST API Endpoints для MCP Tools
# ============================================================================

@mcp.custom_route("/api/search", methods=["POST"])
async def api_search_help(request):
    """REST API: Поиск в справке 1С"""
    return await search_help_handler(request)


@mcp.custom_route("/api/platform/search", methods=["POST"])
async def api_search_platform(request):
    """REST API: Поиск API элементов платформы"""
    return await search_platform_api_handler(request)


@mcp.custom_route("/api/platform/element", methods=["POST"])
async def api_get_element(request):
    """REST API: Получение детальной информации об элементе"""
    return await get_element_handler(request)


@mcp.custom_route("/api/platform/type-members", methods=["POST"])
async def api_get_type_members(request):
    """REST API: Получение членов типа"""
    return await get_type_members_handler(request)


@mcp.custom_route("/api/manage", methods=["POST"])
async def api_manage_help(request):
    """REST API: Управление индексацией"""
    return await manage_help_api_handler(request)


if __name__ == "__main__":
    logger.info(f"🚀 Запуск {SERVER_NAME} на {SERVER_HOST}:{SERVER_PORT}")
    logger.info("📚 Индексация НЕ запускается автоматически. Используйте index_platform_version() для индексации.")
    
    # Используем streamable-http транспорт
    # Настраиваем уровень логирования для uvicorn (access логи будут только в DEBUG)
    if LOG_LEVEL.upper() == "INFO":
        uvicorn_log_level = "warning"
    else:
        uvicorn_log_level = LOG_LEVEL.lower()

    # FastMCP.run() сам управляет event loop
    mcp.run(
        transport="streamable-http",
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level=uvicorn_log_level
    )

