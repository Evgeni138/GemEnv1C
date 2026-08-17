import os
from functools import lru_cache


class Settings:
    """
    Конфигурация лёгкого embedding-сервиса.
    Значения переопределяются через переменные окружения.
    """

    # Модель эмбеддингов (должна давать dim=384 для совместимости с intfloat/multilingual-e5-small)
    embedding_model_name: str

    # Устройство: "cpu" | "gpu" | "auto"
    embedding_device: str

    # Лимиты для batch / корпуса
    max_batch_size: int
    max_corpus_size: int

    # Путь для хранения BM25 статы
    bm25_stats_dir: str

    # Общие опции
    log_level: str

    def __init__(self) -> None:
        self.embedding_model_name = os.getenv(
            "EMBEDDING_MODEL_NAME",
            "intfloat/multilingual-e5-small",
        )
        self.embedding_device = os.getenv("EMBEDDING_DEVICE", "auto").lower()

        self.max_batch_size = int(os.getenv("MAX_BATCH_SIZE", "100"))
        # Справка 1С может быть 25k+ документов; по умолчанию даём запас.
        self.max_corpus_size = int(os.getenv("MAX_CORPUS_SIZE", "50000"))

        # Хранилище BM25 статы — отдельная папка внутри контейнера
        self.bm25_stats_dir = os.getenv(
            "BM25_STATS_DIR",
            "/app/data/bm25-storage",
        )

        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()


@lru_cache()
def get_settings() -> Settings:
    return Settings()

