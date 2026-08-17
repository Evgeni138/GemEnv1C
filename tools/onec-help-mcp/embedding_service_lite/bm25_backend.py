"""
Лёгкая реализация BM25 для embedding-service-lite.
Реализует русскую токенизацию, построение корпуса и расчёт sparse-векторов для гибридного поиска.
"""

import logging
import math
import os
import pickle
import re
from collections import defaultdict
from typing import Any, Dict, List

from .config import get_settings


logger = logging.getLogger(__name__)

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem.snowball import SnowballStemmer

    _NLTK_AVAILABLE = True
except ImportError:  # pragma: no cover - защитный код
    _NLTK_AVAILABLE = False


class RussianTokenizer:
    """
    Токенизатор для русского текста: очистка, стоп-слова, стемминг.
    """

    def __init__(self) -> None:
        if not _NLTK_AVAILABLE:
            raise RuntimeError("nltk required for RussianTokenizer. pip install nltk")
        self.stemmer = SnowballStemmer("russian")
        try:
            import ssl

            _create_unverified = ssl._create_unverified_context
        except Exception:  # pragma: no cover - защитный код
            _create_unverified = None

        if _create_unverified is not None:
            import ssl

            ssl._create_default_https_context = _create_unverified

        try:
            self.stop_words = set(stopwords.words("russian"))
        except LookupError:
            logger.info("Downloading NLTK stopwords...")
            nltk.download("stopwords")
            self.stop_words = set(stopwords.words("russian"))

    def tokenize(self, text: str) -> List[str]:
        text = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = text.split()
        return [self.stemmer.stem(t) for t in tokens if t not in self.stop_words]


class BM25:
    """
    BM25: статистика корпуса, сохранение/загрузка в pickle, расчёт sparse-вектора запроса.
    """

    def __init__(self, stats_path: str, k1: float | None = None, b: float | None = None):
        settings = get_settings()
        self.k1 = k1 if k1 is not None else float(os.getenv("BM25_K1", "1.5"))
        self.b = b if b is not None else float(os.getenv("BM25_B", "0.75"))
        self.stats_path = stats_path
        self.tokenizer = RussianTokenizer()
        self.corpus_stats: Dict[str, Any] = {}
        self.is_built = False
        self._tmp_doc_freq: dict | None = None
        self._tmp_doc_lengths: list | None = None
        self._settings = settings
        self.load_stats()

    def start_incremental_build(self) -> None:
        self._tmp_doc_freq = defaultdict(int)
        self._tmp_doc_lengths = []
        self.is_built = False

    def add_documents(self, corpus: List[str]) -> None:
        if self._tmp_doc_freq is None or self._tmp_doc_lengths is None:
            self.start_incremental_build()
        for doc in corpus:
            tokens = self.tokenizer.tokenize(doc)
            self._tmp_doc_lengths.append(len(tokens))
            for term in set(tokens):
                self._tmp_doc_freq[term] += 1

    def finalize_incremental_build(self) -> bool:
        if not self._tmp_doc_freq or not self._tmp_doc_lengths:
            return False
        doc_freq = self._tmp_doc_freq
        doc_lengths = self._tmp_doc_lengths
        self.corpus_stats = {
            "doc_freq": doc_freq,
            "avg_doc_length": sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0,
            "total_docs": len(doc_lengths),
            "term_to_index": {term: idx for idx, term in enumerate(sorted(doc_freq.keys()))},
        }
        self.is_built = True
        self.save_stats()
        logger.info(
            "BM25 stats built and saved. Vocabulary size: %s",
            len(self.corpus_stats["term_to_index"]),
        )
        self._tmp_doc_freq = None
        self._tmp_doc_lengths = None
        return True

    def build_corpus_stats(self, corpus: List[str]) -> None:
        if not corpus:
            return
        self.start_incremental_build()
        self.add_documents(corpus)
        self.finalize_incremental_build()

    def calculate_sparse_vector(self, text: str) -> Dict[str, Any]:
        if not self.is_built:
            return {"indices": [], "values": []}
        tokens = self.tokenizer.tokenize(text)
        term_counts: dict = defaultdict(int)
        for t in tokens:
            term_counts[t] += 1
        indices: List[int] = []
        values: List[float] = []
        for term, tf in term_counts.items():
            if term not in self.corpus_stats["term_to_index"]:
                continue
            term_index = self.corpus_stats["term_to_index"][term]
            df = self.corpus_stats["doc_freq"].get(term, 0)
            idf = math.log(
                (self.corpus_stats["total_docs"] - df + 0.5) / (df + 0.5) + 1,
            )
            score = idf * (tf * (self.k1 + 1)) / (tf + self.k1)
            if score > 0:
                indices.append(term_index)
                values.append(score)
        return {"indices": indices, "values": values}

    def save_stats(self) -> None:
        if not self.corpus_stats:
            return
        try:
            os.makedirs(os.path.dirname(self.stats_path) or ".", exist_ok=True)
            with open(self.stats_path, "wb") as f:
                pickle.dump(self.corpus_stats, f)
            logger.info("BM25 stats saved to %s", self.stats_path)
        except Exception as e:  # pragma: no cover - защитный код
            logger.error("Error saving BM25 stats: %s", e)

    def load_stats(self) -> None:
        if not os.path.exists(self.stats_path):
            self.is_built = False
            return
        try:
            with open(self.stats_path, "rb") as f:
                self.corpus_stats = pickle.load(f)
            self.is_built = True
            logger.info(
                "BM25 stats loaded from %s. Vocabulary size: %s",
                self.stats_path,
                len(self.corpus_stats.get("term_to_index", {})),
            )
        except Exception as e:  # pragma: no cover - защитный код
            logger.error("Error loading BM25 stats: %s", e)
            self.is_built = False


class BM25Manager:
    """
    Менеджер BM25 по коллекциям: свой корпус и статистика на коллекцию.
    """

    def __init__(self, base_stats_dir: str | None = None) -> None:
        settings = get_settings()
        env_path = os.getenv(
            "BM25_STATS_PATH",
            os.path.join(settings.bm25_stats_dir, "bm25_stats.pkl"),
        )
        if env_path.endswith(".pkl"):
            self.base_stats_dir = os.path.dirname(env_path)
        else:
            self.base_stats_dir = env_path
        if base_stats_dir:
            self.base_stats_dir = base_stats_dir.rstrip("/")
        self.models: Dict[str, BM25] = {}
        try:
            if self.base_stats_dir and not os.path.exists(self.base_stats_dir):
                os.makedirs(self.base_stats_dir, exist_ok=True)
        except (OSError, PermissionError):  # pragma: no cover - защитный код
            logger.warning("Cannot create BM25 stats dir %s", self.base_stats_dir)

    def _get_stats_path(self, collection_name: str) -> str:
        safe = (
            collection_name.replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )
        return os.path.join(self.base_stats_dir, f"bm25_stats_{safe}.pkl")

    def get_model(self, collection_name: str) -> BM25:
        if collection_name not in self.models:
            self.models[collection_name] = BM25(
                stats_path=self._get_stats_path(collection_name),
            )
        return self.models[collection_name]

    def build_corpus(self, collection_name: str, corpus: List[str]) -> bool:
        """Build BM25 corpus with validation."""
        try:
            # Валидация: проверка на пустой корпус
            if not corpus:
                logger.warning(
                    "Empty corpus provided for collection '%s'",
                    collection_name,
                )
                return False

            # Фильтрация пустых и невалидных документов
            valid_docs = [doc.strip() for doc in corpus if doc and doc.strip()]

            if not valid_docs:
                logger.warning(
                    "No valid documents in corpus for collection '%s'. "
                    "Original size: %s, valid: 0",
                    collection_name,
                    len(corpus),
                )
                return False

            # Информирование о фильтрации
            if len(valid_docs) < len(corpus):
                filtered_count = len(corpus) - len(valid_docs)
                logger.info(
                    "Filtered %s empty/invalid documents from corpus "
                    "for '%s' (%s valid documents remain)",
                    filtered_count,
                    collection_name,
                    len(valid_docs),
                )

            # Построение статистики
            self.get_model(collection_name).build_corpus_stats(valid_docs)
            logger.info(
                "BM25 corpus built for '%s' with %s documents",
                collection_name,
                len(valid_docs),
            )
            return True

        except Exception as e:  # pragma: no cover - защитный код
            logger.error("Error building BM25 corpus for '%s': %s", collection_name, e)
            raise

    def calculate_sparse_vector(self, collection_name: str, text: str) -> Dict[str, Any]:
        return self.get_model(collection_name).calculate_sparse_vector(text)

    def is_built(self, collection_name: str) -> bool:
        return collection_name in self.models and self.models[collection_name].is_built


bm25_manager = BM25Manager()

