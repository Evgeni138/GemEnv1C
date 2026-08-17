"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Потокобезопасный статус индексации справки с поддержкой множественных версий
"""

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class IndexingStatus:
    """Статус индексации для конкретной версии платформы"""
    status: str = "idle"  # idle, parsing, building_bm25, vectorizing, completed, error
    version: str = ""
    collection_name: Optional[str] = None
    total_items: int = 0
    processed_items: int = 0
    total_batches: int = 0
    current_batch: int = 0
    points_count: int = 0
    start_time: Optional[datetime] = None
    estimated_time_remaining: float = 0
    error_message: Optional[str] = None


# Глобальное хранилище статусов индексации для разных версий
# Ключ - версия платформы (например, "8.3.26")
_indexing_statuses: Dict[str, IndexingStatus] = {}

# Лок для потокобезопасного доступа к статусам
_status_lock = threading.Lock()


def reset_status(version: str):
    """
    Сброс статуса индексации для конкретной версии

    Args:
        version: Версия платформы (например, "8.3.26")
    """
    with _status_lock:
        _indexing_statuses[version] = IndexingStatus(version=version)


def get_status(version: Optional[str] = None) -> dict:
    """
    Получить текущий статус индексации

    Args:
        version: Версия платформы (опционально). Если не указана, возвращает все статусы.

    Returns:
        Словарь со статусом индексации
    """
    with _status_lock:
        if version is not None:
            # Возвращаем статус конкретной версии
            status_obj = _indexing_statuses.get(version)
            if status_obj is None:
                # Если статус не найден, возвращаем idle статус
                return {
                    "status": "idle",
                    "version": version,
                    "collection_name": None,
                    "total_items": 0,
                    "processed_items": 0,
                    "total_batches": 0,
                    "current_batch": 0,
                    "points_count": 0,
                    "start_time": None,
                    "estimated_time_remaining": 0,
                    "error_message": None
                }

            return {
                "status": status_obj.status,
                "version": status_obj.version,
                "collection_name": status_obj.collection_name,
                "total_items": status_obj.total_items,
                "processed_items": status_obj.processed_items,
                "total_batches": status_obj.total_batches,
                "current_batch": status_obj.current_batch,
                "points_count": status_obj.points_count,
                "start_time": status_obj.start_time.isoformat() if status_obj.start_time else None,
                "estimated_time_remaining": status_obj.estimated_time_remaining,
                "error_message": status_obj.error_message
            }
        else:
            # Возвращаем все статусы
            return {
                ver: {
                    "status": st.status,
                    "version": st.version,
                    "collection_name": st.collection_name,
                    "total_items": st.total_items,
                    "processed_items": st.processed_items,
                    "total_batches": st.total_batches,
                    "current_batch": st.current_batch,
                    "points_count": st.points_count,
                    "start_time": st.start_time.isoformat() if st.start_time else None,
                    "estimated_time_remaining": st.estimated_time_remaining,
                    "error_message": st.error_message
                }
                for ver, st in _indexing_statuses.items()
            }


def update_status(
    version: str,
    status: Optional[str] = None,
    collection_name: Optional[str] = None,
    total_items: Optional[int] = None,
    processed_items: Optional[int] = None,
    total_batches: Optional[int] = None,
    current_batch: Optional[int] = None,
    points_count: Optional[int] = None,
    estimated_time_remaining: Optional[float] = None,
    error_message: Optional[str] = None
):
    """
    Обновить статус индексации для конкретной версии (потокобезопасно)

    Args:
        version: Версия платформы (обязательно)
        status: Новый статус (опционально)
        collection_name: Имя коллекции (опционально)
        total_items: Общее количество элементов (опционально)
        processed_items: Обработано элементов (опционально)
        total_batches: Общее количество батчей (опционально)
        current_batch: Текущий батч (опционально)
        points_count: Количество точек в Qdrant (опционально)
        estimated_time_remaining: Оценочное время до завершения (опционально)
        error_message: Сообщение об ошибке (опционально)
    """
    with _status_lock:
        # Создаем статус если его нет
        if version not in _indexing_statuses:
            _indexing_statuses[version] = IndexingStatus(version=version)

        status_obj = _indexing_statuses[version]

        # Обновляем поля
        if status is not None:
            status_obj.status = status
        if collection_name is not None:
            status_obj.collection_name = collection_name
        if total_items is not None:
            status_obj.total_items = total_items
        if processed_items is not None:
            status_obj.processed_items = processed_items
        if total_batches is not None:
            status_obj.total_batches = total_batches
        if current_batch is not None:
            status_obj.current_batch = current_batch
        if points_count is not None:
            status_obj.points_count = points_count
        if estimated_time_remaining is not None:
            status_obj.estimated_time_remaining = estimated_time_remaining
        if error_message is not None:
            status_obj.error_message = error_message

        # Автоматически устанавливаем start_time при начале индексации
        if status in ["parsing", "building_bm25", "vectorizing"] and status_obj.start_time is None:
            status_obj.start_time = datetime.now()

        # Автоматически вычисляем estimated_time_remaining
        if status_obj.start_time and status_obj.total_batches > 0 and status_obj.current_batch > 0:
            elapsed = (datetime.now() - status_obj.start_time).total_seconds()
            if elapsed > 0:
                avg_time_per_batch = elapsed / status_obj.current_batch
                remaining_batches = status_obj.total_batches - status_obj.current_batch
                status_obj.estimated_time_remaining = remaining_batches * avg_time_per_batch
