# Troubleshooting — Решение проблем

Руководство по диагностике и решению типичных проблем при работе с MCP 1C Help Server.

---

## 🔍 Быстрая диагностика

### Проверка здоровья системы

```bash
# 1. Проверьте статус контейнеров
docker compose ps

# Должно быть:
# onec-help-mcp        running
# onec-help-embedding  running
# onec-help-qdrant     running

# 2. Проверьте health endpoints
curl http://localhost:9063/health
curl http://localhost:8014/health

# 3. Посмотрите логи
docker compose logs onec-help-mcp --tail=50
docker compose logs onec-help-embedding --tail=50
docker compose logs onec-help-qdrant --tail=50
```

---

## 🚨 Проблемы при запуске

### Контейнеры не запускаются

**Симптомы:**
```bash
$ docker compose ps
# Один или несколько контейнеров в статусе "Exited" или "Restarting"
```

**Решение:**

1. **Проверьте логи проблемного контейнера:**
   ```bash
   docker compose logs <имя_контейнера>
   ```

2. **Проверьте порты (не заняты ли):**
   ```bash
   # Windows
   netstat -ano | findstr "9063"
   netstat -ano | findstr "8014"
   netstat -ano | findstr "6347"

   # Linux/Mac
   lsof -i :9063
   lsof -i :8014
   lsof -i :6347
   ```

   Если порты заняты, либо остановите процесс, либо измените порты в `docker-compose.yml`.

3. **Проверьте наличие файлов справки:**
   ```bash
   ls -la data/help1c/8.3.26/
   # Должны быть файлы shcntx_ru.hbk и shcntx_root.hbk
   ```

4. **Пересоздайте контейнеры:**
   ```bash
   docker compose down
   docker compose up -d --force-recreate
   ```

---

### Qdrant падает при старте (panic)

**Симптомы:**
```
qdrant  | panic: invalid type: sequence
qdrant  | thread 'main' panicked at ...
```

**Причина:** Несовместимая версия storage (после обновления Qdrant).

**Решение:**

```bash
# 1. Остановите контейнеры
docker compose down

# 2. Удалите storage Qdrant
rm -rf data/qdrant-storage
# Windows PowerShell:
# Remove-Item -Recurse -Force data\qdrant-storage

# 3. Запустите заново
docker compose up -d

# 4. Выполните индексацию заново
# В Cursor IDE:
# "Вызови manage_platform_help с action='index' и version='8.3.26'"
```

---

### MCP сервер не может подключиться к Qdrant/Embedding

**Симптомы:**
```
Error: Could not connect to Qdrant
Error: Temporary failure in name resolution
```

**Причина:** MCP сервер запущен на хосте (не в Docker), а URL'ы указывают на Docker network.

**Решение:**

Если запускаете MCP сервер **вне Docker**:

1. Создайте/измените `.env`:
   ```bash
   QDRANT_URL=http://localhost:6347
   EMBEDDING_SERVICE_URL=http://localhost:8014
   ```

2. Перезапустите сервер:
   ```bash
   # Если в Docker:
   docker compose restart onec-help-mcp

   # Если на хосте:
   python src/server.py
   ```

---

## 🔎 Проблемы с поиском

### Поиск ничего не находит

**Симптомы:**
- Все поисковые запросы возвращают пустой результат
- Или ошибка: "Для версии платформы X.X.X справка не проиндексирована"

**Диагностика:**

1. **Проверьте, проиндексирована ли версия:**

   В Cursor IDE:
   ```
   💬 "Покажи список проиндексированных версий"
   ```

   Или через API:
   ```bash
   curl http://localhost:9063/help/indexing/status
   ```

2. **Проверьте коллекции в Qdrant:**
   ```bash
   curl http://localhost:6347/collections
   # Должна быть коллекция 1c_help_8_3_26 (или ваша версия)
   ```

**Решение:**

Если версия не проиндексирована:

```
💬 "Вызови manage_platform_help с action='index' и version='8.3.26'"
```

Дождитесь завершения (5-15 минут на CPU, 2-5 минут на GPU).

---

### Поиск возвращает нерелевантные результаты

**Причина:** Слишком общий запрос или нужна переиндексация.

**Решение:**

1. **Уточните запрос:**
   - Вместо "метод" → "метод HTTPЗапрос.Отправить"
   - Вместо "как работать с файлами" → "как прочитать файл в 1С"

2. **Используйте специализированные инструменты:**
   - Для поиска API: `search_1c_platform_api` вместо `search_1c_help`
   - Для конкретного элемента: `get_1c_platform_element`

3. **Попробуйте переиндексацию:**
   ```
   💬 "Вызови manage_platform_help с action='reindex', version='8.3.26' и force=True"
   ```

---

### Ошибка "collection not found"

**Симптомы:**
```json
{"error": "Collection 1c_help_8_3_26 not found"}
```

**Причина:** Версия не проиндексирована или коллекция удалена.

**Решение:**

```
💬 "Вызови manage_platform_help с action='index' и version='8.3.26'"
```

---

## 📊 Проблемы с индексацией

### Индексация зависает или очень медленная

**Симптомы:**
- Индексация идёт > 30 минут
- Или прогресс не меняется

**Диагностика:**

```bash
# 1. Проверьте статус индексации
curl http://localhost:9063/help/indexing/status

# 2. Проверьте нагрузку на систему
docker stats

# 3. Посмотрите логи
docker compose logs onec-help-mcp --tail=100 -f
```

**Решение:**

1. **Если зависла:**
   ```bash
   docker compose restart onec-help-mcp
   # Затем запустите индексацию заново
   ```

2. **Если просто медленно (CPU режим):**
   - Это нормально, индексация на CPU может занимать 10-20 минут
   - Для ускорения переключитесь на GPU режим (см. [DEPLOYMENT.md](DEPLOYMENT.md))

3. **Если постоянно падает:**
   - Проверьте логи embedding сервиса:
     ```bash
     docker compose logs onec-help-embedding --tail=100
     ```
   - Проверьте доступность Qdrant:
     ```bash
     curl http://localhost:6347/collections
     ```

---

### Ошибка "expected dim: 768, got 384"

**Симптомы:**
```
RuntimeError: Expected dimension 768 but got 384
```

**Причина:** Коллекция создана под другую модель эмбеддингов (размерность изменилась).

**Решение:**

```bash
# 1. Остановите контейнеры
docker compose down

# 2. Удалите storage Qdrant (потеряете все индексы!)
rm -rf data/qdrant-storage
# Windows PowerShell:
# Remove-Item -Recurse -Force data\qdrant-storage

# 3. Запустите заново
docker compose up -d

# 4. Переиндексируйте все версии
# В Cursor IDE для каждой версии:
# "Вызови manage_platform_help с action='index' и version='8.3.26'"
```

**Альтернатива (без потери других версий):**

```
💬 "Вызови manage_platform_help с action='reindex', version='8.3.26' и force=True"
```

---

### Ошибка "Out of memory" при индексации

**Симптомы:**
```
FATAL: Out of memory
Killed
```

**Причина:** Недостаточно RAM для контейнера.

**Решение:**

1. **Увеличьте лимиты памяти в Docker:**

   В `docker-compose.yml` добавьте:
   ```yaml
   services:
     onec-help-embedding:
       mem_limit: 4g  # Увеличьте до 4GB или больше
   ```

2. **Уменьшите размер батча:**

   В `.env`:
   ```bash
   MAX_BATCH_SIZE=50  # Вместо 100
   ```

3. **Индексируйте по частям:**
   - Если справка очень большая, разбейте HBK файлы на части

---

## 🔌 Проблемы с Cursor IDE

### Cursor не видит MCP инструменты

**Симптомы:**
- AI не предлагает инструменты 1C Help
- Команды вида "используй search_1c_help" не работают

**Диагностика:**

1. **Проверьте MCP endpoint:**
   ```bash
   curl http://localhost:9063/mcp
   ```

2. **Проверьте конфигурацию Cursor:**

   Файл: `~/.cursor/mcp.json` (Windows: `C:\Users\<имя>\.cursor\mcp.json`)

   Должен содержать:
   ```json
   {
     "mcpServers": {
       "onec-platform-help": {
         "url": "http://localhost:9063/mcp",
         "timeout": 60
       }
     }
   }
   ```

**Решение:**

1. **Проверьте/исправьте mcp.json**

2. **Перезапустите Cursor:**
   - Полностью закройте Cursor
   - Или `Ctrl+Shift+P` → "Reload Window"

3. **Проверьте логи Cursor:**
   - `Help` → `Toggle Developer Tools` → `Console`
   - Ищите ошибки про MCP

---

### Timeout при вызове инструментов

**Симптомы:**
```
Error: Request timeout
Tool execution exceeded 60 seconds
```

**Причина:** Индексация или долгий поиск.

**Решение:**

1. **Увеличьте timeout в mcp.json:**
   ```json
   {
     "mcpServers": {
       "onec-platform-help": {
         "url": "http://localhost:9063/mcp",
         "timeout": 120  // Увеличьте до 120 секунд
       }
     }
   }
   ```

2. **Перезапустите Cursor**

---

## 🐧 Проблемы специфичные для платформ

### Linux: Permission denied для data/

**Симптомы:**
```
Error: Permission denied: 'data/help1c/...'
```

**Решение:**

```bash
# Дайте права на запись для Docker
sudo chmod -R 777 data/

# Или измените владельца (предпочтительнее)
sudo chown -R $(id -u):$(id -g) data/
```

---

### Windows: Долгое скачивание образов

**Симптомы:**
- `docker compose build` занимает > 30 минут

**Решение:**

1. **Используйте WSL2 backend** (быстрее):
   - Docker Desktop → Settings → General → Use WSL2

2. **Увеличьте memory для Docker:**
   - Docker Desktop → Settings → Resources → Memory: 4GB+

---

### macOS M1/M2: Slow performance

**Симптомы:**
- Индексация очень медленная (>30 минут)
- Эмбеддинг сервис тормозит

**Причина:** ARM архитектура, образы собираются для x86_64.

**Решение:**

1. **Используйте ARM-native образы** (если доступны)

2. **Увеличьте ресурсы Docker:**
   - Docker Desktop → Resources → CPUs: 4+, Memory: 8GB+

---

## 🔧 Другие проблемы

### Логи переполняют диск

**Симптомы:**
- Большой размер `data/qdrant-storage/`
- Или логи контейнеров занимают много места

**Решение:**

1. **Ограничьте размер логов Docker:**

   В `/etc/docker/daemon.json`:
   ```json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "10m",
       "max-file": "3"
     }
   }
   ```

   Перезапустите Docker:
   ```bash
   sudo systemctl restart docker
   ```

2. **Очистите старые логи:**
   ```bash
   docker compose down
   docker system prune -a --volumes
   docker compose up -d
   ```

---

### Версия по умолчанию не применяется

**Симптомы:**
- Установили версию по умолчанию, но поиск использует другую

**Решение:**

1. **Проверьте формат версии:**
   ```
   💬 "Вызови manage_platform_help с action='default_set' и version='8.3.26'"
   # НЕ "8.3", а полный формат "8.3.26"!
   ```

2. **Проверьте текущую настройку:**
   ```
   💬 "Вызови manage_platform_help с action='default_get'"
   ```

3. **Проверьте `.env`:**
   ```bash
   cat .env | grep DEFAULT_PLATFORM_VERSION
   # Если установлена там, она перезапишет настройку из manage_platform_help
   ```

---

## 📞 Куда обращаться

Если ни одно решение не помогло:

1. **Проверьте известные проблемы:**
   - [GitHub Issues](https://github.com/rzateev/onec-help-mcp/issues) — возможно проблема уже известна

2. **Соберите диагностику:**
   ```bash
   # Сохраните вывод этих команд
   docker compose ps > debug.txt
   docker compose logs >> debug.txt
   curl http://localhost:9063/health >> debug.txt
   curl http://localhost:9063/help/indexing/status >> debug.txt
   ```

3. **Создайте Issue:**
   - Создайте новый [Issue на GitHub](https://github.com/rzateev/onec-help-mcp/issues/new)
   - Приложите `debug.txt`
   - Опишите шаги воспроизведения
   - Укажите ОС и версию Docker

---

## 🔗 См. также

- [README.md](../README.md) — быстрый старт
- [DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание и настройка
- [TOOLS.md](TOOLS.md) — справочник MCP инструментов
