"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

MCP tool для управления версией платформы по умолчанию
"""

import asyncio
import logging
from typing import Optional
from ..config.default_version import (
    get_default_version_from_config,
    set_default_version_in_config,
    clear_default_version_from_config,
    get_default_version_info
)
from ..config.version import normalize_version, is_version_available

logger = logging.getLogger(__name__)


async def manage_default_platform_version(
    action: str,
    platform_version: Optional[str] = None
) -> str:
    """
    Управление версией платформы по умолчанию
    
    Поддерживает три действия:
    - "set" - установить версию по умолчанию (требуется platform_version)
    - "get" - получить текущую версию по умолчанию
    - "clear" - очистить версию по умолчанию
    
    ⚠️ ВАЖНО:
    - Для action="set" требуется указать platform_version в полном формате (8.3.24, 8.3.26).
      Префикс "8.3" не принимается — только полный номер версии.
    - Версия должна быть доступна (файлы справки в data/help1c/<версия>/)
    - Версия сохраняется в файл конфигурации (default_platform_version.json)
    
    ✅ РАБОТАЕТ:
    - Установка: action="set", platform_version="8.3.24"
    - Получение: action="get"
    - Очистка: action="clear"
    
    Args:
        action: Действие ("set", "get", "clear")
        platform_version: Версия платформы (требуется только для action="set")
        
    Returns:
        Результат выполнения действия
    """
    try:
        action_lower = action.lower().strip()
        
        if action_lower == "get":
            info = await asyncio.to_thread(get_default_version_info)
            version = info.get('version')
            
            if version:
                return f"✅ Версия платформы по умолчанию: {version}\n📁 Файл настроек: {info.get('config_path')}"
            else:
                return f"ℹ️ Версия платформы по умолчанию не установлена.\n💡 Используйте manage_default_platform_version(action='set', platform_version='8.3.24') для установки версии.\n📁 Файл настроек: {info.get('config_path')}"
        
        elif action_lower == "set":
            if not platform_version:
                return "❌ Для action='set' необходимо указать platform_version"
            
            # Нормализуем версию
            normalized_version = normalize_version(platform_version)
            
            # Проверяем, что версия доступна
            if not is_version_available(normalized_version):
                return f"❌ Версия '{normalized_version}' недоступна. Убедитесь, что файлы справки находятся в папке: data/help1c/{normalized_version}/"
            
            # Устанавливаем версию (file I/O в thread)
            if await asyncio.to_thread(set_default_version_in_config, normalized_version):
                return f"✅ Версия платформы по умолчанию установлена: {normalized_version}\n💡 Теперь все запросы без указания версии будут использовать эту версию."
            else:
                return f"❌ Ошибка установки версии платформы по умолчанию"
        
        elif action_lower == "clear":
            if await asyncio.to_thread(clear_default_version_from_config):
                return "✅ Версия платформы по умолчанию очищена.\n💡 Теперь версия будет определяться по приоритетам (заголовки, переменные окружения, последняя доступная)."
            else:
                return "❌ Ошибка очистки версии по умолчанию"
        
        else:
            return f"❌ Неверное действие: '{action}'. Доступные действия: 'set', 'get', 'clear'"
            
    except ValueError as e:
        return f"❌ Неверный формат версии: {str(e)}"
    except Exception as e:
        logger.error(f"❌ Ошибка управления версией по умолчанию: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"❌ Ошибка управления версией по умолчанию: {str(e)}"

