"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tools для работы с API платформы 1С
Реализует инструменты для поиска методов, свойств, типов и конструкторов
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from fastmcp.server.dependencies import get_http_headers

from ..config.version import get_collection_name, get_platform_version, normalize_version
from ..core.api_element import ApiElementType
from ..services.qdrant import get_qdrant_service
from ..services.embedding import get_embedding_service
from .formatter import format_platform_api_search_results, format_platform_element_details

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText

logger = logging.getLogger(__name__)


def _get_headers():
    """Получает HTTP заголовки из FastMCP контекста"""
    try:
        return get_http_headers()
    except (AttributeError, RuntimeError, LookupError):
        # Заголовки недоступны (не в контексте MCP запроса)
        return None


async def _resolve_platform_version(platform_version: Optional[str] = None) -> str:
    """
    Разрешает версию платформы с учетом приоритетов (file I/O в thread).
    1. Параметр tool (наивысший приоритет)
    2. Файл настроек контейнера
    3. Заголовок x-platform-version из mcp.json
    4. Переменная окружения DEFAULT_PLATFORM_VERSION
    5. Последняя доступная версия
    
    Args:
        platform_version: Версия из параметра tool (опционально)
        
    Returns:
        Версия платформы
    """
    headers = _get_headers()
    return await asyncio.to_thread(get_platform_version, headers=headers, tool_param=platform_version)


async def search_1c_platform_api(
    query: str,
    element_type: Optional[str] = None,
    platform_version: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Поиск API элементов платформы 1С (функции, методы, свойства, типы, конструкторы) по имени.
    
    Сначала точное совпадение по имени, затем семантика с фильтром по имени/английскому имени.
    Для латинских запросов (например, "HTTP") при отсутствии совпадений выполняется fallback
    по английским именам элементов (HTTPConnection и т.п.).
    
    ⚠️ ВАЖНО:
    - Ищет только структурированные API элементы (is_api_element=True)
    - Поддерживает фильтрацию по типу элемента (element_type)
    - Для детальной карточки используйте get_1c_platform_element
    
    ✅ РАБОТАЕТ:
    - Поиск функций: query="СтрДлина", element_type="function"
    - Поиск методов: query="Записать", element_type="method"
    - Поиск типов: query="ДокументОбъект", element_type="type"
    - Латинские запросы: query="HTTP" находит HTTPСоединение и связанные элементы
    
    Args:
        query: Поисковый запрос (имя элемента)
        element_type: Тип элемента для фильтрации (type, method, property, constructor, enum, function)
        platform_version: Версия платформы (например, "8.3.24")
        limit: Максимальное количество результатов (по умолчанию 10)
        
    Returns:
        Отформатированные результаты поиска с подсказкой о детальном поиске
    """
    try:
        platform_version = await _resolve_platform_version(platform_version)
        
        collection_name = get_collection_name(platform_version)
        qdrant_service = get_qdrant_service()
        embedding_service = get_embedding_service()

        # Если коллекции для этой версии ещё нет — даём понятное сообщение
        if not await qdrant_service.collection_exists_async(collection_name):
            ver = platform_version
            base_msg = (
                f"❌ Для версии платформы {ver} справка по API не проиндексирована "
                f"(коллекция '{collection_name}' отсутствует в Qdrant).\n"
            )
            hint = (
                f"💡 Сначала вызовите index_platform_version(version='{ver}'), "
                f"либо уберите параметр platform_version, чтобы использовать версию по умолчанию."
            )
            return base_msg + hint
        
        # Создаем фильтр для API элементов
        filter_conditions = [
            FieldCondition(key="is_api_element", match=MatchValue(value=True))
        ]
        
        if element_type:
            filter_conditions.append(
                FieldCondition(key="element_type", match=MatchValue(value=element_type))
            )
        
        # Получаем эмбеддинг для семантического поиска
        query_vector = await embedding_service.get_dense_embedding(query)
        query_lower = query.lower().strip()

        # 1) Точное совпадение по element_name (короткие имена: "Запрос", "Выполнить", "СтрДлина")
        exact_match_filter = Filter(
            must=filter_conditions + [
                FieldCondition(
                    key="element_name",
                    match=MatchValue(value=query)
                )
            ]
        )
        
        exact_results = await qdrant_service.scroll_async(
            collection_name=collection_name,
            scroll_filter=exact_match_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        if exact_results:
            from qdrant_client.models import ScoredPoint
            results = [
                ScoredPoint(id=p.id, score=1.0, payload=p.payload, version=0)
                for p in exact_results
            ]
        else:
            # 2) Точное совпадение по full_name для конструкций вида "Тип.Метод"
            full_name_results = []
            if "." in query:
                full_name_filter = Filter(
                    must=filter_conditions + [
                        FieldCondition(
                            key="full_name",
                            match=MatchValue(value=query)
                        )
                    ]
                )
                full_name_points = await qdrant_service.scroll_async(
                    collection_name=collection_name,
                    scroll_filter=full_name_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                ) or []
                from qdrant_client.models import ScoredPoint
                full_name_results = [
                    ScoredPoint(id=p.id, score=1.0, payload=p.payload, version=0)
                    for p in full_name_points
                ]

            if full_name_results:
                results = full_name_results
            else:
                # 3) Семантический поиск: для коротких/латинских запросов берём больше кандидатов
                candidate_mult = limit * 5 if len(query_lower) <= 8 else limit * 3
                dense_results, _ = await qdrant_service.search_async(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=candidate_mult,
                    filters=Filter(must=filter_conditions)
                )

                # Фильтруем по имени (частичное совпадение по русскому, английскому, full_name)
                filtered_results = []
                for result in dense_results:
                    payload = result.payload
                    element_name = payload.get('element_name', '').lower()
                    element_name_en = payload.get('element_name_en', '').lower()
                    full_name = payload.get('full_name', '').lower()

                    if (query_lower in element_name or
                        query_lower in element_name_en or
                        query_lower in full_name or
                        element_name.startswith(query_lower) or
                        element_name_en.startswith(query_lower)):
                        filtered_results.append(result)
                        if len(filtered_results) >= limit:
                            break

                # 4) Fallback: scroll + filter по имени для латинских/коротких запросов
                if not filtered_results and query.strip().isascii() and len(query_lower) <= 20:
                    scroll_points = await qdrant_service.scroll_async(
                        collection_name=collection_name,
                        scroll_filter=Filter(must=filter_conditions),
                        limit=1000,
                        with_payload=True,
                        with_vectors=False
                    )
                    scroll_points = scroll_points or []
                    from qdrant_client.models import ScoredPoint
                    for point in scroll_points:
                        p = (point.payload if hasattr(point, 'payload') else None) or {}
                        en = (p.get('element_name') or '').lower()
                        en_en = (p.get('element_name_en') or '').lower()
                        fn = (p.get('full_name') or '').lower()
                        if (query_lower in en or query_lower in en_en or query_lower in fn or
                                en.startswith(query_lower) or en_en.startswith(query_lower)):
                            filtered_results.append(ScoredPoint(
                                id=point.id, score=0.9, payload=p, version=0
                            ))
                            if len(filtered_results) >= limit:
                                break

                results = filtered_results[:limit]
        
        # Если ничего не нашли, подсказываем fallback на общий поиск по справке
        if not results:
            hint = (
                f"❌ По запросу '{query}' (тип: {element_type or 'любой'}) "
                f"ничего не найдено в API платформы 1С (версия: {platform_version}).\n"
                f"💡 Попробуйте общий поиск по справке:\n"
                f"   search_1c_help(query='{query}', platform_version='{platform_version}')"
            )
            return hint

        # Используем форматтер для вывода результатов
        return format_platform_api_search_results(
            results=results,
            query=query,
            element_type=element_type,
            platform_version=platform_version,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка поиска: {str(e)}"


async def get_1c_platform_type_members(
    type_name: str,
    platform_version: Optional[str] = None,
    member_type: Optional[str] = None,
    include_constructors: bool = True
) -> str:
    """
    Получение полного списка методов, свойств и конструкторов для типа платформы 1С.
    
    Для части типов (например, ЗаписьJSON) конструкторы в индексе могут отсутствовать —
    это зависит от структуры справки в HBK. Для Запрос, Массив, Структура и др. конструкторы выводятся.
    
    Args:
        type_name: Имя типа (например, "СправочникОбъект", "Запрос")
        platform_version: Версия платформы (например, "8.3.24"). Опционально.
        member_type: Фильтр по типу членов (method, property, constructor). Если не указан — все.
        include_constructors: Включать конструкторы в результат (по умолчанию True).
        
    Returns:
        Отформатированный список методов, свойств и конструкторов с сигнатурами.
    """
    try:
        platform_version = await _resolve_platform_version(platform_version)
        
        collection_name = get_collection_name(platform_version)
        qdrant_service = get_qdrant_service()
        
        # Определяем, какие типы элементов искать
        element_types_to_search = []
        if member_type:
            element_types_to_search = [member_type]
        else:
            element_types_to_search = ['method', 'property']
            if include_constructors:
                element_types_to_search.append('constructor')
        
        # Создаем фильтр для поиска членов типа
        filter_conditions = [
            FieldCondition(key="is_api_element", match=MatchValue(value=True)),
            FieldCondition(key="parent_type", match=MatchValue(value=type_name))
        ]
        
        if len(element_types_to_search) == 1:
            filter_conditions.append(
                FieldCondition(key="element_type", match=MatchValue(value=element_types_to_search[0]))
            )
        else:
            # Ищем несколько типов
            filter_conditions.append(
                Filter(
                    should=[
                        FieldCondition(key="element_type", match=MatchValue(value=et))
                        for et in element_types_to_search
                    ]
                )
            )
        
        query_filter = Filter(must=filter_conditions)
        
        # Получаем все результаты через scroll
        points = await qdrant_service.scroll_async(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            return f"❌ Для типа '{type_name}' не найдено методов, свойств и конструкторов"
        
        # Группируем по типу
        methods = []
        properties = []
        constructors = []
        
        for point in points:
            payload = point.payload
            element_type = payload.get('element_type', '')
            name = payload.get('full_name', payload.get('element_name', 'Unknown'))
            metadata = payload.get('metadata', {})
            details = metadata.get('details', {})
            
            if element_type == 'method':
                methods.append({
                    'name': name,
                    'signature': details.get('signature', ''),
                    'description': payload.get('description', '')
                })
            elif element_type == 'property':
                properties.append({
                    'name': name,
                    'type': details.get('type', 'Unknown'),
                    'description': payload.get('description', '')
                })
            elif element_type == 'constructor':
                constructors.append({
                    'name': name,
                    'signature': details.get('signature', ''),
                    'parameters': details.get('parameters', []),
                    'description': payload.get('description', '')
                })
        
        # Форматируем результаты
        output = [f"✅ Члены типа '{type_name}':\n"]
        
        if constructors:
            output.append(f"\n🔧 Конструкторы ({len(constructors)}):")
            for i, constructor in enumerate(constructors, 1):
                output.append(f"   {i}. {constructor['name']}")
                if constructor.get('signature'):
                    output.append(f"      Сигнатура: {constructor['signature']}")
                if constructor.get('parameters'):
                    output.append(f"      Параметры:")
                    for param in constructor['parameters']:
                        param_str = f"         - {param.get('name', 'Unknown')}"
                        if param.get('type') and param.get('type') != 'Unknown':
                            param_str += f" ({param.get('type')})"
                        if param.get('description'):
                            param_str += f": {param.get('description')}"
                        output.append(param_str)
                if constructor.get('description'):
                    desc = constructor['description'][:150]
                    output.append(f"      Описание: {desc}")
        
        if methods:
            output.append(f"\n📋 Методы ({len(methods)}):")
            for i, method in enumerate(methods, 1):
                output.append(f"   {i}. {method['name']}")
                if method.get('signature'):
                    output.append(f"      Сигнатура: {method['signature']}")
                if method.get('description'):
                    desc = method['description'][:150]
                    output.append(f"      Описание: {desc}")
        
        if properties:
            output.append(f"\n📋 Свойства ({len(properties)}):")
            for i, prop in enumerate(properties, 1):
                output.append(f"   {i}. {prop['name']} ({prop.get('type', 'Unknown')})")
                if prop.get('description'):
                    desc = prop['description'][:150]
                    output.append(f"      Описание: {desc}")
        
        return "\n".join(output)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения членов типа: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка получения членов типа: {str(e)}"


async def get_1c_platform_element(
    element_name: Optional[str] = None,
    element_type: Optional[str] = None,
    parent_type: Optional[str] = None,
    platform_version: Optional[str] = None,
    element_id: Optional[str] = None  # Для обратной совместимости
) -> str:
    """
    Получение полной детальной информации об API элементе (сигнатура, параметры, возвращаемое значение, примеры, доступность).
    
    Поддерживает два формата вызова:
    1. Параметрический (рекомендуется): element_name="Пароль", element_type="property", parent_type="HTTPСоединение"
    2. Через element_id (обратная совместимость): element_id="property_HTTPСоединение_Пароль"
    
    ⚠️ ВАЖНО:
    - Для методов/свойств/конструкторов указывайте parent_type для однозначного поиска
    - При неоднозначности возвращается первый найденный элемент
    - Поле «Возвращает»: до переиндексации у части элементов тип может быть Unknown или скрыт (артефакты парсинга отфильтрованы)
    
    ✅ РАБОТАЕТ:
    - Параметрический формат: element_name="Пароль", element_type="property", parent_type="HTTPСоединение"
    - Короткий формат: element_name="СтрДлина", element_type="function"
    - Старый формат: element_id="property_HTTPСоединение_Пароль"
    
    Args:
        element_name: Имя элемента (например, "Пароль", "СтрДлина", "Записать")
        element_type: Тип элемента (function, method, property, constructor, type, enum)
                     Если не указан, поиск выполняется по всем типам
        parent_type: Родительский тип для методов/свойств/конструкторов (например, "HTTPСоединение")
                    Рекомендуется указывать для точности поиска
        platform_version: Версия платформы (например, "8.3.24")
        element_id: Идентификатор элемента в старом формате (для обратной совместимости)
                   Формат: "function_СтрДлина" или "method_ДокументОбъект_Записать"
        
    Returns:
        Полная детальная информация об элементе
    """
    try:
        platform_version = await _resolve_platform_version(platform_version)
        
        collection_name = get_collection_name(platform_version)
        qdrant_service = get_qdrant_service()
        
        # Если передан element_id (обратная совместимость), парсим его
        if element_id:
            parts = element_id.split('_', 1)
            if len(parts) >= 2:
                element_type = parts[0]
                name_part = parts[1]
                
                # Определяем имя элемента и родительский тип
                if element_type in ['method', 'property', 'constructor']:
                    name_parts = name_part.rsplit('_', 1)
                    if len(name_parts) == 2:
                        parent_type = name_parts[0]
                        element_name = name_parts[1]
                    else:
                        element_name = name_part
                else:
                    element_name = name_part
        
        # Проверяем, что указан хотя бы element_id или element_name
        if not element_id and not element_name:
            return "❌ Необходимо указать либо element_id, либо element_name"
        
        # Формируем фильтр
        filter_conditions = [
            FieldCondition(key="is_api_element", match=MatchValue(value=True)),
            FieldCondition(key="element_name", match=MatchValue(value=element_name))
        ]
        
        if element_type:
            filter_conditions.append(
                FieldCondition(key="element_type", match=MatchValue(value=element_type))
            )
        
        if parent_type:
            filter_conditions.append(
                FieldCondition(key="parent_type", match=MatchValue(value=parent_type))
            )
        
        query_filter = Filter(must=filter_conditions)
        
        # Ищем элемент
        points = await qdrant_service.scroll_async(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=10,  # Получаем несколько для выбора лучшего
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            # Формируем понятное сообщение об ошибке
            search_desc = f"'{element_name}'"
            if parent_type:
                search_desc = f"{parent_type}.{element_name}"
            if element_type:
                search_desc += f" (тип: {element_type})"

            # Подсказка: fallback на общий поиск по справке
            base_query = f"{parent_type}.{element_name}" if parent_type else element_name
            return (
                f"❌ Элемент {search_desc} не найден в API платформы 1С (версия: {platform_version}).\n"
                f"💡 Попробуйте общий поиск по справке:\n"
                f"   search_1c_help(query='{base_query}', platform_version='{platform_version}')"
            )
        
        # Если найден только один элемент или указан parent_type - используем его
        if len(points) == 1 or parent_type:
            point = points[0]
        else:
            # Выбираем элемент с наивысшим приоритетом типа
            # Приоритет: property > method > constructor > function > type
            type_priority = {
                'property': 5,
                'method': 4,
                'constructor': 3,
                'function': 2,
                'type': 1
            }
            
            best_point = None
            best_priority = 0
            
            for p in points:
                payload = p.payload
                elem_type = payload.get('element_type', '')
                priority = type_priority.get(elem_type, 0)
                
                if priority > best_priority:
                    best_priority = priority
                    best_point = p
            
            point = best_point if best_point else points[0]
        
        payload = point.payload
        
        # Формируем element_id для форматтера (для обратной совместимости)
        elem_type = payload.get('element_type', 'unknown')
        elem_name = payload.get('element_name', '')
        parent = payload.get('parent_type')
        
        if parent:
            formatted_element_id = f"{elem_type}_{parent}_{elem_name}"
        else:
            formatted_element_id = f"{elem_type}_{elem_name}"
        
        # Используем форматтер для детальной информации
        return format_platform_element_details(payload, formatted_element_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации об элементе: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка получения информации об элементе: {str(e)}"


async def get_1c_platform_type_constructors(
    type_name: str,
    platform_version: Optional[str] = None
) -> str:
    """
    ⚠️ DEPRECATED: Используйте get_1c_platform_type_members(type_name, include_constructors=True)
    
    Получение конструкторов для создания объектов
    
    Args:
        type_name: Имя типа (например, "СправочникОбъект")
        platform_version: Версия платформы (например, "8.3.24")
        
    Returns:
        Список конструкторов с детальной информацией
    """
    # Перенаправляем на новый метод
    return await get_1c_platform_type_members(
        type_name=type_name,
        platform_version=platform_version,
        member_type="constructor",
        include_constructors=True
    )

