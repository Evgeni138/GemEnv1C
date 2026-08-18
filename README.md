# Gem (1C) — AI Workspace

Портативная AI-конфигурация для разработки на 1С:Предприятие 8.3 на базе [opencode](https://opencode.ai). Содержит 55 skills, документацию по XML-форматам 1С, интеграцию с MCP-серверами (справка платформы, RLM-поиск, YaXUnit-тесты, bsl-analyzer).

Адаптировано из [1c-ai-development-kit](https://github.com/Arman-Kudaibergenov/1c-ai-development-kit) (лицензия AGPL-3.0, см. `.opencode/LICENSE`, `.opencode/ACKNOWLEDGMENTS.md`).

## Возможности

- **55 skills** для работы с объектами метаданных, формами, обработками/отчётами, БСП, СКД, ролями, конфигурациями и расширениями, базами данных, веб-публикацией, тестированием
- **MCP-серверы**: справка платформы 1С 8.3.27 (`onec-help-mcp`), поиск/навигация по исходникам (`rlm-tools-bsl`), справочник платформы (`bsl-analyzer-reference`), запуск YaXUnit-тестов (`metr`)
- **Правила MCP-First и Skills-First** — AI обязан проверять документацию платформы и использовать готовые скиллы вместо изобретения скриптов
- **METR** — сборка и прогон YaXUnit-тестов через Конфигуратор 1С
- **OpenSpec** — формальный процесс спецификаций и изменений

## Структура

```
opencode.jsonc            — конфигурация opencode (MCP-серверы, правила)
AGENTS.md                 — инструкции для AI-ассистента
.opencode/skill/          — 55 skills (SKILL.md + скрипты)
.opencode/docs/           — спецификации и гайды по форматам 1С
scripts/                  — инфраструктурные скрипты
templates/                — шаблоны (.mcp.json и др.)
tools/metr/               — METR: mcp-yaxunit-runner.jar + application.yml (YaXUnit)
tools/onec-help-mcp/      — MCP-сервер справки платформы (Docker compose)
src/cf/                   — выгрузка основной конфигурации (XML)
src/cfe/                  — выгрузки расширений (XML)
src/{configuration,tests,yaxunit} — исходники для сборки METR
dist/                     — собранные артефакты (CF/CFE/EPF)
openspec/                 — процесс OpenSpec (changes/specs/archive)
```

## Требования

- Windows 10/11
- Платформа 1С:Предприятие 8.3 (протестировано: 8.3.24.1467, 8.3.25.1501, 8.3.27.1859)
- [opencode](https://opencode.ai) CLI
- Docker Desktop (для `onec-help-mcp`)
- bsl-analyzer (0.2.67+) — `%LOCALAPPDATA%\Programs\bsl-analyzer\bsl-analyzer.exe`
- JDK 17 (для METR; `C:\Program Files\Java\jdk-17`)
- RLM-сервер поиска по исходникам на `http://127.0.0.1:9000/mcp` (Windows-служба)

## Быстрый старт

```powershell
# 1. Запустить справку платформы 1С (MCP на :9063)
docker compose -f tools/onec-help-mcp/docker-compose.yml up -d

# 2. Проиндексировать справку (первый раз, ~50 мин)
#    Через MCP: manage_platform_help(action="index", version="8.3.27")

# 3. Запустить bsl-analyzer reference
& "$env:LOCALAPPDATA\Programs\bsl-analyzer\bsl-analyzer.exe" mcp serve --profile reference

# 4. Проверить METR (YaXUnit)
& "C:\Program Files\Java\jdk-17\bin\java.exe" -jar tools/metr/mcp-yaxunit-runner.jar

# 5. Открыть рабочее пространство
opencode
```

## MCP-серверы

| Сервер | Транспорт | Назначение |
|--------|-----------|------------|
| `rlm-tools-bsl` | remote `http://127.0.0.1:9000/mcp` | поиск по исходникам конфигурации, call graph, usages |
| `onec-help-mcp` | remote `http://127.0.0.1:9063/mcp` (Docker) | документация платформы 1С (8.3.27) |
| `bsl-analyzer-reference` | local | справочник синтаксиса/типов платформы |
| `bsl-analyzer-workspace` | local (disabled до появления `src/cf`) | поиск по исходникам рабочего пространства |
| `metr` | local (java -jar) | сборка конфигурации, YaXUnit-тесты, синтаксис-проверка |

## Контекст-менеджмент (context-mode)

Встроен как глобальный плагин opencode (v1.0.169, `~/.config/opencode/opencode.jsonc` → `"plugin": ["context-mode"]`).

Что даёт:

- **Знаниевая база сессии** — решения, ошибки, планы, промпты автоматически сохраняются в SQLite (FTS5) и доступны через `ctx_search`
- **Think-in-Code** — песочница `ctx_execute` / `ctx_execute_file`: обработка больших файлов/выводов без засорения контекста, в память попадает только результат
- **Веб-индексация** — `ctx_fetch_and_index` для документации и внешних источников
- **Пакетная обработка** — `ctx_batch_execute` (параллельный запуск команд + автоиндексация вывода)
- **Аналитика** — `ctx_stats` (потребление контекста), `ctx_doctor` (диагностика), дашборд на https://context-mode.com/insight

Команды: `ctx stats` / `ctx doctor` / `ctx upgrade` / `ctx purge` (полный сброс базы).

Хранилище: `C:\Users\popov\.config\opencode\context-mode\{sessions,content}`.

## Известные ограничения

- Skills `1c-web-session`, `playwright-test`, `web-test` требуют MCP-сервер Playwright — в этой среде не установлен, вместо него используется METR
- `bsl-analyzer-workspace` активируется после первой выгрузки конфигурации в `src/cf/`

## Лицензии

- Рабочее пространство и скиллы: AGPL-3.0 (адаптация [1c-ai-development-kit](https://github.com/Arman-Kudaibergenov/1c-ai-development-kit))
- `tools/onec-help-mcp`: MIT (Copyright (c) 2025-2026 Roman Zateev)
