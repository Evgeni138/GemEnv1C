"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

REST API handlers для MCP tools
Предоставляет HTTP REST API для доступа к функциональности MCP сервера
"""

import json
import logging
from typing import Any, Dict

from starlette.requests import Request
from starlette.responses import JSONResponse
from pydantic import ValidationError

from ..tools.validators import (
    SearchRequest,
    PlatformAPISearchRequest,
    GetElementRequest,
    GetTypeMembersRequest,
    ManageHelpRequest
)
from ..tools.search_tool import search_1c_help
from ..tools.platform_tools import (
    search_1c_platform_api,
    get_1c_platform_element,
    get_1c_platform_type_members
)
from ..tools.manage_help_tool import manage_platform_help

logger = logging.getLogger(__name__)


async def _parse_request_body(request: Request) -> Dict[str, Any]:
    """Парсинг тела запроса с обработкой ошибок"""
    try:
        body = await request.body()
        if not body:
            return {}
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")


async def search_help_handler(request: Request) -> JSONResponse:
    """
    POST /api/search
    Поиск в справке 1С

    Body:
    {
        "query": "HTTPЗапрос",
        "platform_version": "8.3.26",  // optional
        "limit": 10  // optional, default 10
    }
    """
    try:
        data = await _parse_request_body(request)

        # Валидация через Pydantic
        validated = SearchRequest(**data)

        # Вызов MCP tool
        result = await search_1c_help(
            query=validated.query,
            platform_version=validated.platform_version,
            limit=validated.limit
        )

        return JSONResponse({
            "success": True,
            "result": result,
            "query": validated.query,
            "limit": validated.limit
        })

    except ValidationError as e:
        logger.warning(f"Validation error in search: {e}")
        return JSONResponse({
            "success": False,
            "error": "Validation error",
            "details": e.errors()
        }, status_code=400)
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error in search handler: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


async def search_platform_api_handler(request: Request) -> JSONResponse:
    """
    POST /api/platform/search
    Поиск API элементов платформы 1С

    Body:
    {
        "query": "HTTPRequest",
        "element_type": "function",  // optional: function, method, property, type, constructor, enum
        "platform_version": "8.3.26",  // optional
        "limit": 10  // optional
    }
    """
    try:
        data = await _parse_request_body(request)

        # Валидация
        validated = PlatformAPISearchRequest(**data)

        # Вызов MCP tool
        result = await search_1c_platform_api(
            query=validated.query,
            element_type=validated.element_type,
            platform_version=validated.platform_version,
            limit=validated.limit
        )

        return JSONResponse({
            "success": True,
            "result": result,
            "query": validated.query,
            "element_type": validated.element_type
        })

    except ValidationError as e:
        logger.warning(f"Validation error in platform search: {e}")
        return JSONResponse({
            "success": False,
            "error": "Validation error",
            "details": e.errors()
        }, status_code=400)
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error in platform search handler: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


async def get_element_handler(request: Request) -> JSONResponse:
    """
    POST /api/platform/element
    Получение детальной информации об API элементе

    Body:
    {
        "element_name": "Пароль",
        "element_type": "property",  // optional
        "parent_type": "HTTPСоединение",  // optional, recommended for methods/properties
        "platform_version": "8.3.26",  // optional
        "element_id": "property_HTTPСоединение_Пароль"  // optional, legacy format
    }
    """
    try:
        data = await _parse_request_body(request)

        # Валидация
        validated = GetElementRequest(**data)

        # Вызов MCP tool
        result = await get_1c_platform_element(
            element_name=validated.element_name,
            element_type=validated.element_type,
            parent_type=validated.parent_type,
            platform_version=validated.platform_version,
            element_id=validated.element_id
        )

        return JSONResponse({
            "success": True,
            "result": result,
            "element_name": validated.element_name,
            "element_type": validated.element_type,
            "parent_type": validated.parent_type
        })

    except ValidationError as e:
        logger.warning(f"Validation error in get element: {e}")
        return JSONResponse({
            "success": False,
            "error": "Validation error",
            "details": e.errors()
        }, status_code=400)
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error in get element handler: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


async def get_type_members_handler(request: Request) -> JSONResponse:
    """
    POST /api/platform/type-members
    Получение списка методов, свойств и конструкторов типа

    Body:
    {
        "type_name": "HTTPСоединение",
        "platform_version": "8.3.26",  // optional
        "member_type": "method",  // optional: method, property, constructor
        "include_constructors": true  // optional, default true
    }
    """
    try:
        data = await _parse_request_body(request)

        # Валидация
        validated = GetTypeMembersRequest(**data)

        # Вызов MCP tool
        result = await get_1c_platform_type_members(
            type_name=validated.type_name,
            platform_version=validated.platform_version,
            member_type=validated.member_type,
            include_constructors=validated.include_constructors
        )

        return JSONResponse({
            "success": True,
            "result": result,
            "type_name": validated.type_name,
            "member_type": validated.member_type
        })

    except ValidationError as e:
        logger.warning(f"Validation error in get type members: {e}")
        return JSONResponse({
            "success": False,
            "error": "Validation error",
            "details": e.errors()
        }, status_code=400)
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error in get type members handler: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)


async def manage_help_handler(request: Request) -> JSONResponse:
    """
    POST /api/manage
    Управление индексацией справки

    Body:
    {
        "action": "list_versions",  // list_versions, index, reindex, status, delete
        "version": "8.3.26"  // required for index, reindex, status, delete
    }
    """
    try:
        data = await _parse_request_body(request)

        # Валидация
        validated = ManageHelpRequest(**data)

        # Вызов MCP tool
        result = await manage_platform_help(
            action=validated.action,
            version=validated.version
        )

        return JSONResponse({
            "success": True,
            "result": result,
            "action": validated.action,
            "version": validated.version
        })

    except ValidationError as e:
        logger.warning(f"Validation error in manage help: {e}")
        return JSONResponse({
            "success": False,
            "error": "Validation error",
            "details": e.errors()
        }, status_code=400)
    except ValueError as e:
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=400)
    except Exception as e:
        logger.error(f"Error in manage help handler: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)
