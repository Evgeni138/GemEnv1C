"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Форматирование результатов поиска API элементов платформы 1С
"""

import re
from typing import List, Dict, Any, Optional

# Паттерн для отсечения ошибочного парсинга "Доступность" как типа возврата
_AVAILABILITY_LIKE = re.compile(
    r"клиент|сервер|соединение|мобильн|веб|толстый|тонкий|автономн|внешнее\s+соединение",
    re.IGNORECASE,
)


def format_platform_api_search_results(
    results: List[Any],
    query: str,
    element_type: Optional[str],
    platform_version: str,
    limit: int
) -> str:
    """
    Форматирование результатов поиска API элементов в компактном формате
    
    Args:
        results: Список результатов поиска (ScoredPoint или подобные объекты)
        query: Поисковый запрос
        element_type: Тип элемента для фильтрации (если был указан)
        platform_version: Версия платформы
        limit: Максимальное количество результатов
        
    Returns:
        Отформатированная строка с результатами
    """
    if not results:
        filter_text = f" (фильтр по типу: {element_type})" if element_type else ""
        return f"❌ По запросу '{query}'{filter_text} ничего не найдено в API платформы 1С (версия: {platform_version})"
    
    formatted_results = []
    filter_text = f" (фильтр по типу: {element_type})" if element_type else ""
    formatted_results.append(
        f"Результаты поиска API элементов по запросу: '{query}'{filter_text} (версия платформы: {platform_version})\n"
    )
    formatted_results.append(
        f"✅ Показано до {limit} результатов (сейчас {len(results)}, параметр limit можно увеличить).\n"
    )
    
    for i, result in enumerate(results, 1):
        # Получаем payload из результата
        if hasattr(result, 'payload'):
            payload = result.payload
            score = result.score if hasattr(result, 'score') else 1.0
        else:
            payload = result
            score = 1.0
        
        # Формируем element_id
        element_type_val = payload.get('element_type', 'unknown')
        element_name = payload.get('element_name', '')
        parent_type = payload.get('parent_type')
        full_name = payload.get('full_name', element_name)
        
        if parent_type:
            element_id = f"{element_type_val}_{parent_type}_{element_name}"
        else:
            element_id = f"{element_type_val}_{element_name}"
        
        # Основная информация
        formatted_results.append(
            f"{i}. element_id: {element_id} | name: {full_name} | type: {element_type_val} | score: {score:.3f}"
        )
        
        # Описание (первые 100-150 символов)
        description = payload.get('description', '')
        if not description:
            # Пытаемся извлечь из content или text
            description = payload.get('content', payload.get('text', ''))
        
        if description:
            desc_short = description[:150] + ('...' if len(description) > 150 else '')
            formatted_results.append(f"   Описание: {desc_short}")
        
        # Сигнатура для функций/методов
        signature = payload.get('metadata', {}).get('details', {}).get('signature', '')
        if not signature and element_type_val in ['function', 'method']:
            # Пытаемся извлечь из content
            content = payload.get('content', '')
            if content and ('Синтаксис:' in content or 'Syntax:' in content):
                import re
                sig_match = re.search(r'(?:Синтаксис|Syntax):\s*([^\n]+)', content)
                if sig_match:
                    signature = sig_match.group(1).strip()[:100]
        
        if signature:
            formatted_results.append(f"   Сигнатура: {signature[:100]}")
        
        # Родительский тип
        if parent_type:
            formatted_results.append(f"   Родительский тип: {parent_type}")
        
        # Версия платформы
        since_version = payload.get('metadata', {}).get('details', {}).get('since_version', '')
        if since_version:
            formatted_results.append(f"   Доступно с версии: {since_version}")
        
        formatted_results.append("")  # Пустая строка между результатами
    
    # Подсказка о детальном поиске и возможной "фаззивости"
    if results:
        first_result = results[0]
        payload = first_result.payload if hasattr(first_result, 'payload') else first_result
        element_type_val = payload.get('element_type', 'unknown')
        element_name = payload.get('element_name', '')
        parent_type = payload.get('parent_type')

        # Если нет точного совпадения (все score < 1.0), подсветим, что поиск не по точному имени
        try:
            scores = [
                (r.score if hasattr(r, 'score') else 1.0)
                for r in results
            ]
        except Exception:
            scores = [1.0]
        if scores and max(scores) < 0.999:
            formatted_results.append(
                "⚠ Имя элемента не совпало точно, показаны ближайшие совпадения по имени/семантике.\n"
            )

        formatted_results.append(
            f"💡 Для получения полной информации используйте:\n"
            f"   get_1c_platform_element(element_name='{element_name}', element_type='{element_type_val}', parent_type='{parent_type or None}')"
        )
    
    return "\n".join(formatted_results)


def format_platform_element_details(
    payload: Dict[str, Any],
    element_id: str
) -> str:
    """
    Форматирование детальной информации об API элементе
    
    Args:
        payload: Payload элемента из Qdrant
        element_id: Идентификатор элемента
        
    Returns:
        Отформатированная строка с детальной информацией
    """
    payload = payload or {}
    details = (payload.get("metadata") or {}).get("details") or {}
    output = []

    element_type = payload.get('element_type', 'unknown')
    element_name = payload.get('element_name', '')
    full_name = payload.get('full_name', element_name)
    parent_type = payload.get('parent_type')
    
    # Заголовок
    output.append(f"✅ **{full_name}**")
    output.append(f"\n📌 Тип: {element_type}")
    
    if parent_type:
        output.append(f"📦 Родительский тип: {parent_type}")
    
    # Английское имя
    name_en = payload.get('element_name_en', '')
    if name_en:
        output.append(f"🌐 Английское имя: {name_en}")
    
    # Сигнатура
    signature = details.get('signature', '')
    if signature:
        # Очищаем сигнатуру от лишнего текста, оставляем только основную часть
        import re
        sig_clean = signature
        
        # Ищем закрывающую скобку - это конец сигнатуры
        # Паттерн: ИмяФункции(параметры) - обрезаем до закрывающей скобки включительно
        match = re.search(r'^([^(]+\([^)]*\))', sig_clean)
        if match:
            sig_clean = match.group(1)
        else:
            # Если не нашли скобки, обрезаем до первого маркера
            for marker in ['Параметры:', 'Возвращаемое значение:', 'Описание:', 'Parameters:', 'Return value:', 'Description:']:
                if marker in sig_clean:
                    sig_clean = sig_clean.split(marker)[0].strip()
                    break
        
        # Если сигнатура все еще слишком длинная, обрезаем
        if len(sig_clean) > 200:
            sig_clean = sig_clean[:200] + '...'
        
        if sig_clean:
            output.append(f"\n🔧 Сигнатура:")
            output.append(sig_clean)
    
    # Параметры
    parameters = details.get('parameters') or []
    if parameters:
        output.append(f"\n📋 Параметры:")
        for param in parameters:
            param_name = param.get('name', 'Unknown')
            param_type = param.get('type', 'Unknown')
            param_desc = param.get('description', '')
            required = param.get('required', False)
            req_text = " (обязательный)" if required else " (необязательный)"
            output.append(f"   - {param_name}: {param_type}{req_text}")
            if param_desc:
                output.append(f"     {param_desc[:100]}")
    
    # Возвращаемое значение (исключаем ошибочный парсинг "Доступность" как типа/описания)
    return_type = details.get('return_type') or ''
    return_description = details.get('return_description') or ''
    if not isinstance(return_type, str):
        return_type = str(return_type) if return_type else ''
    if not isinstance(return_description, str):
        return_description = str(return_description) if return_description else ''
    if return_type and _AVAILABILITY_LIKE.search(return_type):
        return_description = (return_type + " " + return_description).strip() if return_description else return_type
        return_type = ""
    if return_description and _AVAILABILITY_LIKE.search(return_description):
        return_description = ""
    if return_type or return_description:
        output.append(f"\n↩️ Возвращает:")
        if return_type:
            output.append(f"   Тип: {return_type}")
        if return_description:
            output.append(f"   {return_description[:200]}")
    
    # Описание
    description = payload.get('description', '')
    if not description:
        description = payload.get('content', payload.get('text', ''))
    
    if description:
        output.append(f"\n📝 Описание:")
        # Очищаем описание от лишних пробелов и обрезаем до разумной длины
        desc_clean = ' '.join(description.split())
        # Убираем дублирование информации из сигнатуры
        if signature:
            sig_start = signature.split('Параметры:')[0].split('Возвращаемое значение:')[0].strip()
            if sig_start and sig_start in desc_clean:
                desc_clean = desc_clean.replace(sig_start, '').strip()
        # Ограничиваем длину и добавляем многоточие если нужно
        if len(desc_clean) > 500:
            desc_clean = desc_clean[:500] + '...'
        output.append(desc_clean)
    
    # Примеры
    examples = details.get('examples') or []
    if examples:
        output.append(f"\n💡 Примеры:")
        for example in examples[:3]:  # Показываем максимум 3 примера
            if example:
                example_clean = example.strip()[:200]
                output.append(f"   {example_clean}")
    
    # Специфичные поля для свойств
    if element_type == 'property':
        if details.get('type'):
            output.append(f"\n📊 Тип: {details.get('type')}")
        
        if details.get('read_only'):
            output.append("🔒 Только чтение")
        if details.get('write_only'):
            output.append("✏️ Только запись")
    
    # Примечания (для всех типов элементов)
    notes = details.get('notes') or ''
    if notes:
        output.append(f"\n💬 Примечание:")
        notes_clean = ' '.join(notes.split())
        if len(notes_clean) > 300:
            notes_clean = notes_clean[:300] + '...'
        output.append(notes_clean)
    
    # Доступность (для всех типов элементов)
    availability = details.get('availability') or ''
    if availability:
        output.append(f"\n🌐 Доступность: {availability}")
    
    # Связанные элементы
    related_elements = details.get('related_elements') or []
    if related_elements:
        output.append(f"\n🔗 См. также:")
        for related in related_elements[:5]:  # Показываем максимум 5 связанных элементов
            if related:
                output.append(f"   - {related}")
    
    # Версия платформы
    since_version = details.get('since_version') or ''
    deprecated = details.get('deprecated', False)
    deprecated_since = details.get('deprecated_since') or ''
    
    if since_version:
        output.append(f"\n📅 Доступно с версии: {since_version}")
    
    if deprecated:
        dep_text = f" (устарел с версии {deprecated_since})" if deprecated_since else " (устарел)"
        output.append(f"⚠️ Устарел{dep_text}")
    
    # Источник
    file_path = payload.get('file_path', '')
    if file_path:
        output.append(f"\n📁 Источник: {file_path}")
    
    return "\n".join(output)

