# REST API Documentation

HTTP REST API для доступа к функциональности MCP сервера без необходимости подключения MCP сессии.

## 🎯 Зачем нужен REST API?

- ✅ Использование в Claude Code skills без MCP подключения
- ✅ Простые curl запросы для тестирования
- ✅ Интеграция с другими сервисами и скриптами
- ✅ Та же функциональность, что и MCP tools

## 📡 Base URL

```
http://localhost:9063
```

## 🔍 Endpoints

### 1. Поиск в справке 1С

**Endpoint:** `POST /api/search`

**Описание:** Гибридный поиск (BM25 + семантический) по справке 1С

**Request Body:**
```json
{
  "query": "HTTPЗапрос",
  "platform_version": "8.3.26",  // опционально
  "limit": 10                     // опционально, default: 10, max: 100
}
```

**Response:**
```json
{
  "success": true,
  "result": "✅ Показано до 10 результатов...",
  "query": "HTTPЗапрос",
  "limit": 10
}
```

**Примеры:**

```bash
# Базовый поиск
curl -X POST http://localhost:9063/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "HTTPЗапрос", "limit": 3}'

# Поиск с указанием версии
curl -X POST http://localhost:9063/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Работа с XML", "platform_version": "8.3.26", "limit": 5}'
```

<details>
<summary><b>Пример реального ответа</b></summary>

```json
{
  "success": true,
  "result": "✅ Показано до 3 результатов по запросу 'HTTPЗапрос'...\n\n1. **HTTPЗапрос** (релевантность: 0.917)\n   📄 Тип: type\n   📝 Описание: Предназначен для описания HTTP-запросов...\n   📁 Файл: shcntx_ru.hbk:objects/catalog63/catalog578/catalog2125/HTTPRequest.html\n   🔢 Версия платформы: 8.3.26\n\n2. **HTTPСервисЗапрос** (релевантность: 0.915)...",
  "query": "HTTPЗапрос",
  "limit": 3
}
```

</details>

---

### 2. Поиск API элементов платформы

**Endpoint:** `POST /api/platform/search`

**Описание:** Поиск структурированных API элементов (функции, методы, свойства, типы)

**Request Body:**
```json
{
  "query": "HTTPConnection",
  "element_type": "type",         // опционально: function, method, property, type, constructor, enum
  "platform_version": "8.3.26",   // опционально
  "limit": 10                      // опционально
}
```

**Response:**
```json
{
  "success": true,
  "result": "✅ Найдено API элементов...",
  "query": "HTTPConnection",
  "element_type": "type"
}
```

**Примеры:**

```bash
# Поиск типа
curl -X POST http://localhost:9063/api/platform/search \
  -H "Content-Type: application/json" \
  -d '{"query": "HTTPСоединение", "element_type": "type"}'

# Поиск функции
curl -X POST http://localhost:9063/api/platform/search \
  -H "Content-Type: application/json" \
  -d '{"query": "СтрДлина", "element_type": "function"}'

# Поиск методов (с увеличенным лимитом)
curl -X POST http://localhost:9063/api/platform/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Записать", "element_type": "method", "limit": 20}'
```

<details>
<summary><b>Пример ответа для типа</b></summary>

```json
{
  "success": true,
  "result": "✅ Найдено API элементов по запросу: 'HTTPСоединение' (тип: type)\n\n1. element_id: type_HTTPСоединение | name: HTTPСоединение | type: type | score: 1.000\n   Описание: Предназначен для взаимодействия с внешними системами по протоколу HTTP...\n   Доступно с версии: 8.0.\n\n💡 Для получения полной информации используйте:\n   get_1c_platform_element(element_name='HTTPСоединение', element_type='type')",
  "query": "HTTPСоединение",
  "element_type": "type"
}
```

</details>

---

### 3. Получение детальной информации об элементе

**Endpoint:** `POST /api/platform/element`

**Описание:** Полная карточка API элемента с сигнатурой, параметрами, примерами

**Request Body:**
```json
{
  "element_name": "Пароль",
  "element_type": "property",      // опционально
  "parent_type": "HTTPСоединение", // опционально, рекомендуется для методов/свойств
  "platform_version": "8.3.26",    // опционально
  "element_id": "property_HTTPСоединение_Пароль"  // опционально, legacy формат
}
```

**Response:**
```json
{
  "success": true,
  "result": "📄 Детальная информация об элементе...",
  "element_name": "Пароль",
  "element_type": "property",
  "parent_type": "HTTPСоединение"
}
```

**Примеры:**

```bash
# Получить информацию о свойстве
curl -X POST http://localhost:9063/api/platform/element \
  -H "Content-Type: application/json" \
  -d '{
    "element_name": "Пароль",
    "element_type": "property",
    "parent_type": "HTTPСоединение"
  }'

# Получить информацию о функции
curl -X POST http://localhost:9063/api/platform/element \
  -H "Content-Type: application/json" \
  -d '{
    "element_name": "СтрДлина",
    "element_type": "function"
  }'

# Используя legacy формат
curl -X POST http://localhost:9063/api/platform/element \
  -H "Content-Type: application/json" \
  -d '{
    "element_id": "property_HTTPСоединение_Пароль"
  }'
```

---

### 4. Получение членов типа

**Endpoint:** `POST /api/platform/type-members`

**Описание:** Список всех методов, свойств и конструкторов типа

**Request Body:**
```json
{
  "type_name": "HTTPСоединение",
  "platform_version": "8.3.26",    // опционально
  "member_type": "method",          // опционально: method, property, constructor
  "include_constructors": true      // опционально, default: true
}
```

**Response:**
```json
{
  "success": true,
  "result": "✅ Члены типа 'HTTPСоединение'...",
  "type_name": "HTTPСоединение",
  "member_type": "method"
}
```

**Примеры:**

```bash
# Все члены типа
curl -X POST http://localhost:9063/api/platform/type-members \
  -H "Content-Type: application/json" \
  -d '{
    "type_name": "HTTPСоединение"
  }'

# Только методы
curl -X POST http://localhost:9063/api/platform/type-members \
  -H "Content-Type: application/json" \
  -d '{
    "type_name": "Запрос",
    "member_type": "method"
  }'

# Только свойства
curl -X POST http://localhost:9063/api/platform/type-members \
  -H "Content-Type: application/json" \
  -d '{
    "type_name": "ДокументОбъект",
    "member_type": "property"
  }'
```

---

### 5. Управление индексацией

**Endpoint:** `POST /api/manage`

**Описание:** Управление версиями и индексацией справки

**Request Body:**
```json
{
  "action": "list_versions",  // list_versions, index, reindex, status, delete
  "version": "8.3.26"          // обязательно для index, reindex, status, delete
}
```

**Response:**
```json
{
  "success": true,
  "result": "✅ Доступные версии...",
  "action": "list_versions",
  "version": null
}
```

**Примеры:**

```bash
# Список доступных версий
curl -X POST http://localhost:9063/api/manage \
  -H "Content-Type: application/json" \
  -d '{
    "action": "list_versions"
  }'

# Индексация версии
curl -X POST http://localhost:9063/api/manage \
  -H "Content-Type: application/json" \
  -d '{
    "action": "index",
    "version": "8.3.26"
  }'

# Статус индексации
curl -X POST http://localhost:9063/api/manage \
  -H "Content-Type: application/json" \
  -d '{
    "action": "status",
    "version": "8.3.26"
  }'

# Переиндексация (пересоздание)
curl -X POST http://localhost:9063/api/manage \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reindex",
    "version": "8.3.26"
  }'

# Удаление индекса
curl -X POST http://localhost:9063/api/manage \
  -H "Content-Type: application/json" \
  -d '{
    "action": "delete",
    "version": "8.3.26"
  }'
```

---

## 🔧 Health Check

**Endpoint:** `GET /health`

**Описание:** Проверка работоспособности сервиса

**Response:**
```json
{
  "status": "healthy",
  "service": "MCP 1C Help Server",
  "version": "2.0.0",
  "qdrant": "OK",
  "embedding_service": "OK",
  "available_versions": 2,
  "versions": ["8.3.26", "8.3.25"]
}
```

**Пример:**
```bash
curl http://localhost:9063/health
```

---

## 📊 Статус индексации

**Endpoint:** `GET /help/indexing/status`

**Описание:** Детальный статус текущей индексации

**Response:**
```json
{
  "status": "idle",
  "version": null,
  "indexed_versions": [
    {
      "version": "8.3.26",
      "points_count": 15234,
      "status": "green"
    }
  ],
  "active_indexing": []
}
```

**Пример:**
```bash
curl http://localhost:9063/help/indexing/status
```

---

## 🚨 Обработка ошибок

### Validation Error (400)

```json
{
  "success": false,
  "error": "Validation error",
  "details": [
    {
      "loc": ["query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Server Error (500)

```json
{
  "success": false,
  "error": "Internal server error: ..."
}
```

---

## 🔐 Валидация

Все запросы проходят валидацию через Pydantic модели:

- **query**: 1-500 символов, обязательно
- **limit**: 1-100, default: 10
- **platform_version**: формат X.Y.Z (например, "8.3.26")
- **element_type**: один из: function, method, property, type, constructor, enum
- **action**: один из: list_versions, index, reindex, status, delete

---

## 💡 Использование в Claude Code Skills

```python
import httpx

async def search_1c_help(query: str, limit: int = 10):
    """Поиск в справке 1С через REST API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9063/api/search",
            json={"query": query, "limit": limit}
        )
        data = response.json()
        return data["result"]

# Использование
result = await search_1c_help("HTTPЗапрос", limit=5)
print(result)
```

---

## 🔄 Сравнение: MCP vs REST API

| Функция | MCP Protocol | REST API |
|---------|--------------|----------|
| **Поиск в справке** | `search_1c_help()` | `POST /api/search` |
| **Поиск API** | `search_1c_platform_api()` | `POST /api/platform/search` |
| **Детали элемента** | `get_1c_platform_element()` | `POST /api/platform/element` |
| **Члены типа** | `get_1c_platform_type_members()` | `POST /api/platform/type-members` |
| **Управление** | `manage_platform_help()` | `POST /api/manage` |
| **Использование** | Claude Desktop, Cursor IDE | curl, httpx, любой HTTP клиент |
| **Валидация** | Встроенная (FastMCP) | Pydantic validators |

---

## 📚 См. также

- [TOOLS.md](TOOLS.md) - Документация MCP tools
- [README.md](../README.md) - Общая информация о проекте
- [ARCHITECTURE.md](ARCHITECTURE.md) - Архитектура системы
