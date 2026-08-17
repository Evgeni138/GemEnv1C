# Развёртывание MCP 1C Help Server

## Режимы работы

| Режим | Описание | Qdrant | Embedding | Базовый образ |
|-------|----------|--------|-----------|----------------|
| **CPU** (по умолчанию) | Локальный Qdrant и встроенный embedding-service-lite (CPU) | Qdrant v1.16.3 (`onec-help-qdrant`, порт 6347) | `onec-help-embedding` (`http://onec-help-embedding:8004`, порт 8014) | `python:3.12-slim` |
| **GPU** | То же, но embedding-service-lite на GPU | Qdrant v1.16.3 (`onec-help-qdrant`, порт 6347) | `onec-help-embedding-gpu` (CUDA 12.8, порт 8014) | PyTorch 2.7 + CUDA 12.8 |

---

## Режим CPU (по умолчанию)

```bash
docker compose build
docker compose up -d
```

Поднимутся контейнеры: `onec-help-mcp`, `onec-help-embedding`, `onec-help-qdrant`.

## Режим GPU

Требуется NVIDIA Docker Runtime и поддерживаемая GPU.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

Контейнер `onec-help-embedding-gpu` собирается из `Dockerfile.embedding-lite-gpu` с `EMBEDDING_DEVICE=gpu` (fallback на CPU, если CUDA недоступен).

---

## Порты и URL

| Компонент | Внутри Docker | С хоста |
|-----------|---------------|---------|
| MCP сервер | `http://onec-help-mcp:9063` | `http://localhost:9063` |
| Qdrant | `http://onec-help-qdrant:6333` | `http://localhost:6347` |
| Embedding | `http://onec-help-embedding:8004` | `http://localhost:8014` |

---

## Диагностика

**Сервис не стартует**  
`docker compose logs onec-help-mcp`

**Ошибки при индексации**  
- Embedding: `curl http://localhost:8014/health`
- Qdrant: `docker compose ps` (контейнер `onec-help-qdrant` должен быть Up)

**Поиск не находит результаты**  
Выполнить индексацию через MCP-тул `index_platform_version`. Проверить файлы в `data/help1c/<версия>/`.

**`Temporary failure in name resolution`**  
Если MCP-сервер на хосте (не в Docker), в `.env` укажите:
- `QDRANT_URL=http://localhost:6347`
- `EMBEDDING_SERVICE_URL=http://localhost:8014`

**Qdrant падает при старте (panic, `invalid type: sequence`)**  
Несовместимая версия storage. Решение:
1. Удалить `data/qdrant-storage`
2. Перезапустить: `docker compose restart onec-help-qdrant`
3. Выполнить индексацию заново

**Переключение режима (CPU ↔ GPU)**  
Пересобрать с нужными compose-файлами:
- CPU: `docker compose build`
- GPU: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml build`

---

## См. также

- [README.md](../README.md) — быстрый старт, инструменты MCP, переменные окружения.
