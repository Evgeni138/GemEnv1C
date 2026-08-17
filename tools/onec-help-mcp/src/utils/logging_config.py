"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Конфигурация structured logging с поддержкой JSON формата
"""

import logging
import os
import sys
from pythonjsonlogger import jsonlogger


def setup_logging(log_level: str = "INFO", use_json: bool = True):
    """
    Настройка логирования для приложения

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        use_json: Использовать JSON формат (для production)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Создаем handler
    handler = logging.StreamHandler(sys.stdout)

    if use_json:
        # JSON формат для production (удобно парсить в системах логирования)
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
            rename_fields={
                "asctime": "timestamp",
                "name": "logger",
                "levelname": "level"
            }
        )
    else:
        # Обычный формат для development
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    handler.setFormatter(formatter)

    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Подавляем шумные библиотеки
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Логируем настройку
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "json_format": use_json
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Получить настроенный logger

    Args:
        name: Имя logger (обычно __name__)

    Returns:
        Configured logger
    """
    return logging.getLogger(name)
