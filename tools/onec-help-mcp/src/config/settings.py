"""
MCP 1C Help Server
SPDX-License-Identifier: MIT
Copyright (c) 2025-2026 Roman Zateev

Конфигурация для MCP сервера справки 1С
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Версионирование платформы
DEFAULT_PLATFORM_VERSION = os.getenv("DEFAULT_PLATFORM_VERSION", None)
HELP_BASE_PATH = Path(os.getenv("HELP_BASE_PATH", "/app/data/help1c"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/app/cache"))

# Embedding Service
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://onec-help-embedding:8004")
EMBEDDING_REQUEST_TIMEOUT = int(os.getenv("EMBEDDING_REQUEST_TIMEOUT", "10"))
# Таймаут для batch (50 текстов на CPU может занимать 60–120 с)
EMBEDDING_BATCH_TIMEOUT = int(os.getenv("EMBEDDING_BATCH_TIMEOUT", "120"))

# Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://onec-help-qdrant:6333")
QDRANT_REQUEST_TIMEOUT = int(os.getenv("QDRANT_REQUEST_TIMEOUT", "30"))

# Server settings
SERVER_NAME = os.getenv("SERVER_NAME", "MCP 1C Help Server")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "9063"))

# Search settings
DEFAULT_SEARCH_LIMIT = int(os.getenv("DEFAULT_SEARCH_LIMIT", "10"))
MAX_SEARCH_LIMIT = int(os.getenv("MAX_SEARCH_LIMIT", "100"))  # Достаточно большой лимит, но не безграничный
USE_HYBRID_SEARCH = os.getenv("USE_HYBRID_SEARCH", "true").lower() == "true"

# Hybrid search settings
SPARSE_VECTOR_NAME = os.getenv("SPARSE_VECTOR_NAME", "sparse_bm25")
SPARSE_BOOST = float(os.getenv("SPARSE_BOOST", "0.5"))
RRF_K = int(os.getenv("RRF_K", "60"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOGS_PATH = os.getenv("LOGS_PATH", "/app/logs")

