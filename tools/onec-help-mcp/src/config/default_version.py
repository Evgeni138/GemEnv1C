"""
Управление версией платформы по умолчанию
Хранится в файле настроек контейнера
"""

import json
import logging
from pathlib import Path
from typing import Optional
from .settings import CACHE_DIR

logger = logging.getLogger(__name__)

# Путь к файлу настроек версии по умолчанию
# Используем директорию cache, которая доступна для записи
DEFAULT_VERSION_CONFIG_PATH = CACHE_DIR / "default_platform_version.json"


def get_default_version_from_config() -> Optional[str]:
    """
    Получает версию платформы по умолчанию из файла настроек
    
    Returns:
        Версия платформы или None если не установлена
    """
    try:
        if DEFAULT_VERSION_CONFIG_PATH.exists():
            with open(DEFAULT_VERSION_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                version = config.get('platform_version')
                if version:
                    logger.debug(f"Версия из файла настроек: {version}")
                    return version
    except Exception as e:
        logger.warning(f"Ошибка чтения файла настроек версии: {e}")
    
    return None


def set_default_version_in_config(version: str) -> bool:
    """
    Устанавливает версию платформы по умолчанию в файл настроек
    
    Args:
        version: Версия платформы (например, "8.3.24")
        
    Returns:
        True если успешно, False иначе
    """
    try:
        # Создаем директорию если не существует
        DEFAULT_VERSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем конфигурацию
        config = {
            'platform_version': version
        }
        
        with open(DEFAULT_VERSION_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Версия платформы по умолчанию установлена: {version}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения версии в файл настроек: {e}")
        return False


def clear_default_version_from_config() -> bool:
    """
    Очищает версию платформы по умолчанию из файла настроек
    
    Returns:
        True если успешно, False иначе
    """
    try:
        if DEFAULT_VERSION_CONFIG_PATH.exists():
            DEFAULT_VERSION_CONFIG_PATH.unlink()
            logger.info("✅ Версия платформы по умолчанию очищена")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка очистки версии из файла настроек: {e}")
        return False


def get_default_version_info() -> dict:
    """
    Получает информацию о версии по умолчанию
    
    Returns:
        Словарь с информацией о версии
    """
    version = get_default_version_from_config()
    return {
        'version': version,
        'config_path': str(DEFAULT_VERSION_CONFIG_PATH),
        'exists': DEFAULT_VERSION_CONFIG_PATH.exists()
    }

