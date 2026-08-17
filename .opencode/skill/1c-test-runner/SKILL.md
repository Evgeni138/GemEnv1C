---
name: 1c-test-runner
description: >
  Этот скилл MUST быть вызван когда пользователь говорит "напиши тест", "протестируй модуль", "запусти unit-тесты" для 1С.
  SHOULD также вызывать после реализации бизнес-логики для верификации через 1c-ai-debug MCP.
  Do NOT использовать для UI-тестов — используй playwright-test или 1c-web-session.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, mcp__1c-ai-debug__run_unit_tests, mcp__1c-ai-debug__execute_1c_code
---

# /1c-test-runner — AI-тестирование 1С без внешних зависимостей

Workflow для автономного тестирования бизнес-логики 1С:
- AI создаёт тестовые данные через `1c-ai-debug` MCP (CRUD)
- AI пишет тест — CommonModule с суффиксом `_Test`
- Тест загружается в базу через `/db-load-xml` + `/db-update`
- AI запускает через MCP инструмент `run_unit_tests`
- Результат возвращается текстом/JSON — без скриншотов, без vanessa-runner

## Предварительные требования

- `1c-ai-debug` MCP подключён к проекту
- Расширение AI_Debug установлено и опубликовано в базе

## Стек

```
Claude → 1c-ai-debug MCP (run_unit_tests) → 1С база
              ↑
         BSL: CommonModule *_Test (пишет Claude)
              ↑
         CRUD: create_catalog_item, create_document, post_document
```

---

## Шаг 1 — Создать тестовые данные

```json
{"name": "create_catalog_item", "arguments": {"catalogName": "Контрагенты", "data": {"Наименование": "TEST-001"}}}

{"name": "create_document", "arguments": {
  "documentType": "ПоступлениеТоваровУслуг",
  "header": {"Контрагент": "<ref>", "Дата": "2026-01-01T00:00:00"},
  "tables": {"Товары": [{"Номенклатура": "<ref>", "Количество": 10, "Цена": 100}]}
}}

{"name": "post_document", "arguments": {"documentType": "ПоступлениеТоваровУслуг", "documentRef": "<ref>"}}
```

---

## Шаг 2 — Написать тест

Тест — CommonModule с суффиксом `_Test`. Пример модуля `AI_SelfTest_Test` уже в составе AI_Debug.

```bsl
// CommonModules/ТестПроведенияПоступления_Test/Ext/Module.bsl

#Область СлужебныйПрограммныйИнтерфейс

Процедура ИсполняемыеСценарии() Экспорт
    ЮТТесты.ДобавитьТест("ПроведениеПоступленияФормируетДвижения");
КонецПроцедуры

Процедура ПроведениеПоступленияФормируетДвижения() Экспорт
    // Arrange — ссылка из шага 1
    ДокументСсылка = ПредопределённоеЗначение("...");  // или передать через параметры

    // Act + Assert
    Движения = РегистрыНакопления.ТоварыНаСкладах.СоздатьНаборЗаписей();
    Движения.Отбор.Регистратор.Установить(ДокументСсылка);
    Движения.Прочитать();

    ЮТУтверждения.Больше(Движения.Количество(), 0, "Ожидаются движения по регистру");
КонецПроцедуры

#КонецОбласти
```

### API ЮТУтверждения (прямые вызовы)

```bsl
ЮТУтверждения.Равно(Факт, Ожидаемое, "комментарий")
ЮТУтверждения.НеРавно(Факт, НеОжидаемое)
ЮТУтверждения.ЭтоИстина(Условие, "комментарий")
ЮТУтверждения.ЭтоЛожь(Условие)
ЮТУтверждения.Больше(Значение, Порог, "комментарий")
ЮТУтверждения.Меньше(Значение, Порог)
ЮТУтверждения.НеЗаполнено(Значение)
ЮТУтверждения.Заполнено(Значение)
ЮТУтверждения.ИмеетДлину(Коллекция, N)
```

> ⚠️ Fluent-стиль (`ЮТУтверждения.Что(X).Равно(Y)`) не работает в CommonModule — нет self-reference.

### Добавить тест в конфигурацию

```xml
<!-- Configuration.xml → ChildObjects -->
<CommonModule>ТестПроведенияПоступления_Test</CommonModule>
```

CommonModule флаги: `Server=true`, `ClientManagedApplication=false`.

---

## Шаг 3 — Загрузить в базу

```
/db-load-xml <configDir> -Mode Partial -Files "CommonModules/ТестПроведенияПоступления_Test.xml,CommonModules/ТестПроведенияПоступления_Test/Ext/Module.bsl"
/db-update
```

---

## Шаг 4 — Запустить тесты

```json
// Все _Test модули
{"name": "run_unit_tests", "arguments": {}}

// Конкретный модуль
{"name": "run_unit_tests", "arguments": {"moduleName": "ТестПроведенияПоступления_Test"}}
```

### Формат результата

```json
{
  "success": true,
  "total": 3,
  "passed": 3,
  "failed": 0,
  "summary": "[OK] ПроведениеПоступленияФормируетДвижения\n[OK] ..."
}
```

При `failed > 0` — `success: false`, в `summary` строки `[FAIL] ИмяТеста: текст ошибки`.

---

## Шаг 5 — Cleanup

```json
{"name": "delete_object", "arguments": {"objectType": "Documents", "objectName": "ПоступлениеТоваровУслуг", "objectRef": "<ref>"}}
{"name": "delete_object", "arguments": {"objectType": "Catalogs", "objectName": "Контрагенты", "objectRef": "<ref>"}}
```

---

## Полный пример (end-to-end)

```
1. create_catalog_item(Номенклатура, {Наименование: "TEST-001"}) → ref_ном
2. create_document(ПоступлениеТоваровУслуг, {Товары: [{Номенклатура: ref_ном, Кол: 5, Цена: 200}]}) → ref_doc
3. post_document(ПоступлениеТоваровУслуг, ref_doc) → success: true
4. Claude пишет BSL тест → /db-load-xml + /db-update
5. run_unit_tests({moduleName: "ТестПроведенияПоступления_Test"}) → {success: true, passed: 1}
6. delete_object x2 (cleanup)
```

---

## Ограничения

- Тесты только серверная бизнес-логика: расчёты, движения, проведение — не UI
- Тест загружается в базу до запуска через `/db-load-xml` + `/db-update`
- Ссылки между объектами — GUID-строки из ответов create_*
- `post_document` требует `РежимЗаписиДокумента.Проведение` — база должна допускать проведение

## Связанные скилы

- `/db-load-xml` — загрузить тест-модуль в базу
- `/db-update` — применить к БД
- `1c-ai-debug` MCP — CRUD данных и запуск `run_unit_tests`
