"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Унифицированный MCP tool для управления версиями платформы и индексами справки 1С.

Цель: не засорять список MCP-инструментов десятком служебных тулов,
а дать один "админский" вход с понятным action.
"""

import logging
from typing import Optional

from .version_tools import (
    list_platform_versions,
    get_platform_version_info,
)
from .indexing_tools import (
    index_platform_version,
    reindex_platform_version,
)
from .default_version_tool import manage_default_platform_version

logger = logging.getLogger(__name__)


async def manage_platform_help(
    action: str,
    version: Optional[str] = None,
    show_indexed_only: Optional[bool] = None,
    force: Optional[bool] = None,
) -> str:
    """
    Управляемый тул для всех операций с версиями платформы и индексами справки.

    Доступные действия (action):

    - "list" / "list_versions"
        Показать все доступные версии и их статус индексации.
        Опционально: show_indexed_only=True — только проиндексированные.

    - "list_indexed"
        Список только проиндексированных версий
        (аналог list_platform_versions(show_indexed_only=True)).

    - "info" / "version_info"
        Информация по конкретной версии.
        Требует: version="8.3.26".

    - "index"
        Индексация справки для версии.
        Требует: version="8.3.26".

    - "reindex"
        Переиндексация справки для версии.
        Требует: version="8.3.26".
        Дополнительно: force=True для принудительного удаления старой коллекции.

    - "default_get"
        Получить текущую версию платформы по умолчанию.

    - "default_set"
        Установить версию платформы по умолчанию.
        Требует: version="8.3.26" (полный номер).

    - "default_clear"
        Очистить версию платформы по умолчанию.

    Args:
        action: Строковый идентификатор действия (см. выше).
        version: Версия платформы, когда это требуется (8.3.26 и т.п.).
        show_indexed_only: Для действий list/list_versions — показывать только проиндексированные.
        force: Для reindex — принудительно пересоздавать коллекцию.

    Returns:
        Отформатированный текстовый результат выбранного действия.
    """
    act = (action or "").strip().lower()

    try:
        # --- Список версий ---
        if act in ("list", "list_versions"):
            return await list_platform_versions(show_indexed_only=bool(show_indexed_only))

        if act in ("list_indexed", "list_indexed_only"):
            return await list_platform_versions(show_indexed_only=True)

        # --- Информация по версии ---
        if act in ("info", "version_info"):
            if not version:
                return "❌ Для action='info' требуется параметр version, например '8.3.26'."
            return await get_platform_version_info(version)

        # --- Индексация / переиндексация ---
        if act in ("index", "index_version"):
            if not version:
                return "❌ Для action='index' требуется параметр version, например '8.3.26'."
            return await index_platform_version(version)

        if act in ("reindex", "reindex_version"):
            if not version:
                return "❌ Для action='reindex' требуется параметр version, например '8.3.26'."
            return await reindex_platform_version(version, force=bool(force))

        # --- Версия по умолчанию ---
        if act in ("default_get", "get_default"):
            return await manage_default_platform_version(action="get")

        if act in ("default_set", "set_default"):
            if not version:
                return "❌ Для action='default_set' требуется параметр version, например '8.3.26'."
            return await manage_default_platform_version(action="set", platform_version=version)

        if act in ("default_clear", "clear_default"):
            return await manage_default_platform_version(action="clear")

        # --- Неверное действие ---
        return (
            f"❌ Неверное действие: '{action}'. Поддерживаемые действия:\n"
            f"   - list, list_versions\n"
            f"   - list_indexed\n"
            f"   - info, version_info\n"
            f"   - index, reindex\n"
            f"   - default_get, default_set, default_clear\n"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка в manage_platform_help(action={action}, version={version}): {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка выполнения действия '{action}': {str(e)}"

