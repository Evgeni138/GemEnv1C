"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Логика работы с версиями платформы 1С
"""

import re
import logging
from pathlib import Path
from typing import Optional, List
from .settings import HELP_BASE_PATH, DEFAULT_PLATFORM_VERSION
from .default_version import get_default_version_from_config

logger = logging.getLogger(__name__)


def normalize_version(version: str) -> str:
    """
    Нормализует версию платформы (убирает лишние символы, проверяет формат)
    
    Args:
        version: Версия в формате "8.3.24" или "8_3_24"
        
    Returns:
        Нормализованная версия в формате "8.3.24"
        
    Raises:
        ValueError: Если формат версии неверный
    """
    version = version.strip()
    
    # Заменяем подчеркивания на точки
    version = version.replace('_', '.')
    
    # Проверяем формат версии (например, 8.3.24)
    if re.match(r'^\d+\.\d+\.\d+', version):
        # Берем только первые три числа (8.3.24)
        parts = version.split('.')[:3]
        return '.'.join(parts)
    
    raise ValueError(f"Неверный формат версии платформы: {version}. Ожидается формат: 8.3.24")


def get_platform_version(headers: dict = None, tool_param: str = None) -> str:
    """
    Определяет версию платформы с учетом приоритетов:
    1. Параметр tool (наивысший приоритет)
    2. Файл настроек контейнера (/app/config/default_platform_version.json)
    3. Заголовок x-platform-version из mcp.json
    4. Переменная окружения DEFAULT_PLATFORM_VERSION
    5. Последняя доступная версия
    
    Args:
        headers: HTTP заголовки запроса
        tool_param: Параметр platform_version из MCP tool
        
    Returns:
        Версия платформы в формате "8.3.24"
    """
    # 1. Параметр tool (наивысший приоритет)
    if tool_param:
        tool_param = tool_param.strip()
        try:
            version = normalize_version(tool_param)
            logger.debug(f"Версия из параметра tool: {version}")
            return version
        except ValueError:
            pass
        # Префикс вида "8.3" → последняя доступная 8.3.x
        if re.match(r'^\d+\.\d+$', tool_param.replace('_', '.')):
            resolved = _resolve_version_prefix(tool_param)
            if resolved:
                logger.debug(f"Версия из параметра tool (префикс {tool_param!r}): {resolved}")
                return resolved
            logger.warning(f"Неверный формат версии в параметре tool: {tool_param!r}. Ожидается 8.3.24 или префикс 8.3")
    
    # 2. Файл настроек контейнера
    config_version = get_default_version_from_config()
    if config_version:
        try:
            version = normalize_version(config_version)
            logger.debug(f"Версия из файла настроек: {version}")
            return version
        except ValueError as e:
            logger.warning(f"Неверный формат версии в файле настроек: {e}")
    
    # 3. Заголовок MCP запроса (x-platform-version из mcp.json)
    if headers:
        platform_version = headers.get('x-platform-version')
        if platform_version:
            try:
                version = normalize_version(platform_version)
                logger.debug(f"Версия из заголовка x-platform-version: {version}")
                return version
            except ValueError as e:
                logger.warning(f"Неверный формат версии в заголовке: {e}")
    
    # 4. Переменная окружения
    if DEFAULT_PLATFORM_VERSION:
        try:
            version = normalize_version(DEFAULT_PLATFORM_VERSION)
            logger.debug(f"Версия из переменной окружения: {version}")
            return version
        except ValueError as e:
            logger.warning(f"Неверный формат версии в переменной окружения: {e}")
    
    # 5. Последняя доступная версия
    latest_version = get_latest_available_version()
    if latest_version:
        logger.debug(f"Используется последняя доступная версия: {latest_version}")
        return latest_version
    
    # Если ничего не найдено
    raise ValueError("Не удалось определить версию платформы. Укажите версию через параметр platform_version, файл настроек, заголовок x-platform-version или переменную окружения DEFAULT_PLATFORM_VERSION")


def _resolve_version_prefix(prefix: str) -> Optional[str]:
    """
    Разрешает префикс версии (например, "8.3") в последнюю доступную полную версию (8.3.26).
    """
    prefix = prefix.replace('_', '.')
    if not re.match(r'^\d+\.\d+$', prefix):
        return None
    available = get_available_versions()
    matching = [v for v in available if v.startswith(prefix + '.')]
    return matching[0] if matching else None


def get_latest_available_version() -> Optional[str]:
    """
    Получает последнюю доступную версию платформы из папки help1c
    
    Returns:
        Версия платформы или None если версии не найдены
    """
    if not HELP_BASE_PATH.exists():
        logger.warning(f"Папка справки не найдена: {HELP_BASE_PATH}")
        return None
    
    # Находим все папки с версиями
    version_dirs = []
    for item in HELP_BASE_PATH.iterdir():
        if item.is_dir():
            dir_name = item.name
            # Проверяем формат версии (8.3.24 или 8_3_24)
            if re.match(r'^\d+[._]\d+[._]\d+', dir_name):
                try:
                    version = normalize_version(dir_name)
                    version_dirs.append((version, item))
                except ValueError:
                    continue
    
    if not version_dirs:
        logger.warning(f"Не найдено папок с версиями в {HELP_BASE_PATH}")
        return None
    
    # Сортируем по версии (последняя версия)
    version_dirs.sort(key=lambda x: tuple(map(int, x[0].split('.'))), reverse=True)
    
    latest_version = version_dirs[0][0]
    logger.info(f"Найдено {len(version_dirs)} версий платформы. Последняя: {latest_version}")
    
    return latest_version


def get_available_versions() -> List[str]:
    """
    Получает список всех доступных версий платформы
    
    Returns:
        Список версий в формате ["8.3.24", "8.3.25", ...]
    """
    if not HELP_BASE_PATH.exists():
        return []
    
    versions = []
    for item in HELP_BASE_PATH.iterdir():
        if item.is_dir():
            dir_name = item.name
            if re.match(r'^\d+[._]\d+[._]\d+', dir_name):
                try:
                    version = normalize_version(dir_name)
                    versions.append(version)
                except ValueError:
                    continue
    
    # Сортируем по версии
    versions.sort(key=lambda x: tuple(map(int, x.split('.'))), reverse=True)
    
    return versions


def get_collection_name(version: str) -> str:
    """
    Формирует имя коллекции Qdrant для версии платформы
    
    Args:
        version: Версия платформы (например, "8.3.24")
        
    Returns:
        Имя коллекции (например, "1c_help_8_3_24")
    """
    version_normalized = version.replace('.', '_')
    return f"1c_help_{version_normalized}"


def get_help_path_for_version(version: str) -> Path:
    """
    Получает путь к папке со справкой для конкретной версии
    
    Args:
        version: Версия платформы (например, "8.3.24")
        
    Returns:
        Путь к папке со справкой
    """
    # Нормализуем версию (получаем формат с точками: 8.3.24)
    normalized_version = normalize_version(version)
    
    # Проверяем оба формата (8.3.24 и 8_3_24)
    path_with_dots = HELP_BASE_PATH / normalized_version
    path_with_underscores = HELP_BASE_PATH / normalized_version.replace('.', '_')
    
    # Возвращаем существующий путь или путь с точками по умолчанию
    if path_with_dots.exists():
        return path_with_dots
    elif path_with_underscores.exists():
        return path_with_underscores
    else:
        # По умолчанию возвращаем путь с точками (стандартный формат)
        return path_with_dots


def is_version_available(version: str) -> bool:
    """
    Проверяет, доступна ли версия платформы
    
    Args:
        version: Версия платформы
        
    Returns:
        True если версия доступна, False иначе
    """
    try:
        normalized_version = normalize_version(version)
        help_path = get_help_path_for_version(normalized_version)
        return help_path.exists() and help_path.is_dir()
    except ValueError:
        return False

