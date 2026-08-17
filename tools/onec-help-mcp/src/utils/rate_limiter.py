"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Rate limiting для предотвращения одновременных тяжелых операций
Использует asyncio.Semaphore для ограничения параллельных индексаций
"""

import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class IndexingRateLimiter:
    """Ограничитель одновременных индексаций"""

    def __init__(self, max_concurrent: int = 1):
        """
        Args:
            max_concurrent: Максимальное количество одновременных индексаций
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_indexing: dict[str, bool] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, version: str):
        """
        Получить разрешение на индексацию версии

        Args:
            version: Версия платформы

        Yields:
            True если разрешение получено

        Raises:
            RuntimeError: Если версия уже индексируется
        """
        # Проверяем, не индексируется ли уже эта версия
        async with self._lock:
            if self._active_indexing.get(version, False):
                raise RuntimeError(
                    f"Версия {version} уже индексируется. "
                    f"Дождитесь завершения или остановите текущую индексацию."
                )
            self._active_indexing[version] = True

        logger.info(f"Запрошено разрешение на индексацию версии {version}")

        # Ждем доступный слот
        async with self._semaphore:
            logger.info(f"Получено разрешение на индексацию версии {version}")
            try:
                yield True
            finally:
                # Освобождаем версию
                async with self._lock:
                    self._active_indexing[version] = False
                logger.info(f"Индексация версии {version} завершена, разрешение освобождено")

    async def is_indexing(self, version: str) -> bool:
        """
        Проверить, индексируется ли версия в данный момент

        Args:
            version: Версия платформы

        Returns:
            True если версия индексируется
        """
        async with self._lock:
            return self._active_indexing.get(version, False)

    async def get_active_indexing(self) -> list[str]:
        """
        Получить список версий, которые индексируются в данный момент

        Returns:
            Список версий
        """
        async with self._lock:
            return [v for v, active in self._active_indexing.items() if active]


# Глобальный экземпляр rate limiter
_indexing_limiter: Optional[IndexingRateLimiter] = None


def get_indexing_limiter() -> IndexingRateLimiter:
    """Получить глобальный rate limiter для индексации"""
    global _indexing_limiter
    if _indexing_limiter is None:
        # Максимум 1 индексация одновременно (можно настроить через env)
        import os
        max_concurrent = int(os.getenv("MAX_CONCURRENT_INDEXING", "1"))
        _indexing_limiter = IndexingRateLimiter(max_concurrent=max_concurrent)
    return _indexing_limiter
