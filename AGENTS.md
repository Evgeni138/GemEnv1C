# Gem (1C) — AI Workspace Configuration

## О проекте

Портативная AI-конфигурация для разработки на 1С:Предприятие 8.3. Содержит 55 skills, документацию по XML форматам, интеграцию с MCP-серверами (help, память, YaXUnit-тесты, bsl-analyzer).

Адаптировано из https://github.com/Arman-Kudaibergenov/1c-ai-development-kit (лицензия AGPL-3.0, см. `.opencode/LICENSE`, `.opencode/ACKNOWLEDGMENTS.md`).

## Структура

```
opencode.jsonc      — конфигурация opencode (MCP-серверы)
.opencode/skill/    — 55 skills (SKILL.md + скрипты)
.opencode/docs/     — спецификации и гайды по форматам 1С
scripts/            — инфраструктурные скрипты
templates/          — шаблоны (.mcp.json и др.)
tools/metr/         — METR: mcp-yaxunit-runner.jar + application.yml (YaXUnit)
tools/onec-help-mcp/ — MCP-сервер справки платформы (Docker)
```

## MANDATORY: MCP-First Rule

### Когда какой MCP-инструмент использовать

| Ситуация | MCP-сервер | Действие |
|----------|-----------|----------|
| Нужна документация синтаксиса/методов платформы 1С | `onec-help-mcp` | Вызвать `helpsearch` (или REST `/api/search` на :9063) ДО написания кода |
| Нужна навигация по модулям платформы (стандартные подсистемы, типовые) | `bsl-analyzer-reference` | Поиск по модулям платформы |
| Поиск по исходникам конфигурации проекта | `bsl-analyzer-workspace` | Поиск по `src/cf` (профиль отключён, пока нет `src/cf`) |
| Нужно вспомнить контекст проекта | `rlm-tools-bsl` | Вызвать `rlm_route_context` в начале сессии |
| Запуск/просмотр YaXUnit-тестов | `metr` | Провайдер тестов YaXUnit (разборка/сборка/тест) |

### Непоколебимые правила (в 1С-проектах)

- **НИКОГДА** не писать 1С-код, не проверив сначала `onec-help-mcp` (`helpsearch`) по синтаксису
- **НИКОГДА** не пропускать проверку синтаксиса BSL после написания кода
- Если MCP-сервер недоступен — сказать об этом явно, не делать тихий fallback

### MCP vs Grep

| Задача | Использовать |
|--------|--------------|
| Поиск по исходникам проекта | Grep/Glob |
| Поиск по XML метаданных 1С | Grep/Glob |
| Документация платформы / синтаксис | `onec-help-mcp` |
| Модули платформы | `bsl-analyzer-reference` |

## MANDATORY: Skills-First Rule

**ПЕРЕД написанием любого скрипта, кода или решения — проверить, существует ли skill.**

Workflow:
1. Пользователь просит что-то → просмотреть список скиллов ниже
2. Skill существует → использовать инструмент Skill сразу, НЕ изобретать заново
3. Нет skill → только тогда писать свой код

Это относится ко ВСЕМ операциям 1С: создание баз, загрузка конфигураций, компиляция объектов, работа с формами, БСП, СКД, ролями и т.д. **Никогда не генерировать свои PowerShell/BAT-скрипты для операций, которые покрыты скиллами.**

## MANDATORY: Автономность после одобрения

**Одна точка одобрения на задачу. После «ок» пользователя — выполнять автономно.**

- Задавать уточняющие вопросы ДО показа плана
- Показать дизайн+план → получить ОДНО одобрение
- После «ок»: не спрашивать «можно ли продолжить с шага N?», «всё ли ок?», «продолжать ли?»
- Останавливаться только на блокерах (невозможно продолжить, противоречивые требования)
- Отчитываться о результатах в конце

## Маршрутизация задач (автоматическая)

| Сложность | Режим | Что делать |
|-----------|-------|-----------|
| 1-2 объекта, очевидно | **прямой** | Использовать скиллы напрямую, без церемоний |
| 3-5 задач, нужен дизайн | **standard** | brainstorm → краткий план → выполнение |
| 6+ задач, архитектурные | **full** | brainstorm → write-plan → subagent-dev |
| Формальные спецификации | **openspec** | openspec-proposal → openspec-apply |

## Скиллы (ключевые)

### Объекты метаданных
- `meta-compile`, `meta-edit`, `meta-remove` — CRUD для 23 типов объектов
- `inspect` — анализ структуры объекта (реквизиты, ТЧ, формы, движения, типы)

### Формы
- `form-compile`, `form-edit`, `form-add`, `form-patterns`, `help-add`

### Обработки и отчёты
- `epf-expert` (init/build/dump/add-form/bsp-init/bsp-add-command), `erf-expert`

### БСП
- `bsp-patterns` — паттерны работы с подсистемами БСП

### СКД и макеты
- `skd-compile`, `skd-edit`, `mxl-expert`, `img-grid`

### Роли
- `role-expert` (compile/validate), `inspect` — аудит прав роли (Rights.xml, RLS)

### Конфигурация и расширения
- `cf-init`, `cf-edit`, `cfe-init`, `cfe-borrow`, `cfe-patch-method`, `cfe-diff`, `validate`

### База данных
- `db-create`, `db-list`, `db-dump-cf`, `db-load-cf`, `db-dump-xml`, `db-load-xml`, `db-update`, `db-run`, `db-load-git`

### Веб (Apache-публикация)
- `web-publish`, `web-unpublish`, `web-info`, `web-stop`

### Тестирование
- `1c-test-runner` — AI-тестирование бизнес-логики (модели через MCP; YaXUnit-тесты запускает `metr`)
- `validate` — валидация XML-структур объектов

### Workflow
- `brainstorm` — основной: обсуждение → план → автономное выполнение
- `write-plan` — создать tasks.md из design.md
- `subagent-dev` — выполнить tasks.md субагентами
- `1c-help-mcp` — поиск по документации платформы (требует onec-help-mcp)
- `1c-query-opt` — оптимизация запросов

### OpenSpec
- `openspec-proposal`, `openspec-apply`, `openspec-archive`

### ⚠️ Недоступные скиллы (требуют playwright MCP — НЕ установлен)
`1c-web-session`, `playwright-test`, `web-test` — эти скиллы рассчитаны на MCP-сервер Playwright, который в этом проекте заменён на METR (YaXUnit). Не использовать, пока Playwright не подключён.

## Правила разработки

### 1С кодирование
- Следовать стандартам БСП и ITS
- Кириллица для кода 1С (BSL), латиница для инфраструктуры
- Табы для отступов в BSL коде
- UTF-8 BOM для PowerShell-скриптов с кириллицей

### Workflow доработок
- Для любых доработок: `brainstorm` (сам выберет режим express/standard/full)
- Для формальных спецификаций: `openspec-proposal` → `openspec-apply`
- Одно одобрение → автономная реализация → отчёт в конце
- НИКОГДА не спрашивать разрешения после одобрения плана

### Git безопасность
- НИКОГДА force push на main/master
- НЕ коммитить .env, credentials, ключи
- НЕ пропускать hooks без явного запроса
- Предупреждать перед деструктивными операциями

### Контекст
- RLM-first: проверять `rlm_route_context` перед чтением файлов
- Сохранять решения в RLM после завершения задач

## MCP-серверы (конфигурация в `opencode.jsonc`)

| Сервер | Транспорт | Статус |
|--------|-----------|--------|
| `rlm-tools-bsl` | remote HTTP `http://127.0.0.1:9000/mcp` (Windows-служба) | active |
| `onec-help-mcp` | remote HTTP `http://127.0.0.1:9063/mcp` (Docker compose) | после `docker compose up -d` |
| `bsl-analyzer-reference` | local (`bsl-analyzer mcp serve --profile reference`) | active |
| `bsl-analyzer-workspace` | local (`--profile workspace --source-dir src/cf`) | disabled до появления `src/cf` |
| `metr` | local (java -jar tools/metr/mcp-yaxunit-runner.jar, JDK 17) | active (placeholders в tools/metr/application.yml) |

### Запуск вручную
```powershell
# onec-help-mcp
docker compose -f tools/onec-help-mcp/docker-compose.yml up -d

# METR (проверка)
& "C:\Program Files\Java\jdk-17\bin\java.exe" -jar tools/metr/mcp-yaxunit-runner.jar

# bsl-analyzer
& "$env:LOCALAPPDATA\Programs\bsl-analyzer\bsl-analyzer.exe" mcp serve --profile reference
```

## Инфраструктура

- Платформы 1С: `C:\Program Files\1cv8\8.3.24.1467`, `8.3.25.1501`, `8.3.27.1859`
- bsl-analyzer: `%LOCALAPPDATA%\Programs\bsl-analyzer\bsl-analyzer.exe` (0.2.67)
- JDK: `C:\Program Files\Java\jdk-17` (для METR; java не в PATH)
- Спpaвка платформы 1С 8.3.27: `tools/onec-help-mcp/data/help1c/8.3.27/` (.hbk, не в git)