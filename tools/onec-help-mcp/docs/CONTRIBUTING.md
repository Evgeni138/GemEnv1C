# Contributing Guide

Руководство для разработчиков проекта.

## 🛠️ Настройка окружения

### 1. Клонирование и установка

```bash
git clone https://github.com/rzateev/onec-help-mcp.git
cd onec-help-mcp

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements-base.txt
pip install -r requirements-dev.txt
```

### 2. Pre-commit hooks

```bash
# Установка pre-commit
pip install pre-commit

# Настройка hooks
pre-commit install

# Проверка (опционально)
pre-commit run --all-files
```

## ✅ Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Конкретный файл
pytest tests/test_version.py

# Конкретный тест
pytest tests/test_version.py::TestVersionNormalization::test_normalize_full_version

# Только unit тесты
pytest -m unit

# Только integration тесты
pytest -m integration
```

### Проверка покрытия

```bash
# Генерация HTML отчета
pytest --cov=src --cov-report=html

# Открыть отчет
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux
```

## 🎨 Форматирование и линтинг

### Black (форматирование)

```bash
# Проверка
black --check src tests

# Применить
black src tests
```

### Flake8 (линтинг)

```bash
# Проверка
flake8 src tests

# С игнорированием определенных ошибок
flake8 src tests --extend-ignore=E501
```

### isort (сортировка импортов)

```bash
# Проверка
isort --check-only src tests

# Применить
isort src tests
```

### Все вместе (автоматически)

Pre-commit hooks автоматически запускаются при `git commit`:

```bash
git add .
git commit -m "feat: добавил новую функцию"
# Pre-commit автоматически проверит и исправит код
```

Если хотите запустить вручную:

```bash
pre-commit run --all-files
```

## 📝 Стиль кода

### Python

- **Line length**: 120 символов
- **Форматтер**: Black
- **Импорты**: isort с профилем black
- **Docstrings**: Google style

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Краткое описание функции.

    Более подробное описание того, что делает функция.

    Args:
        param1: Описание первого параметра
        param2: Описание второго параметра

    Returns:
        Описание возвращаемого значения

    Raises:
        ValueError: Когда param2 < 0
        RuntimeError: Когда что-то пошло не так

    Examples:
        >>> function_name("test", 10)
        True
    """
    pass
```

### Именование

- **Переменные/функции**: `snake_case`
- **Классы**: `PascalCase`
- **Константы**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### Type hints

Всегда используйте type hints:

```python
from typing import Optional, List, Dict, Any

def search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    pass
```

## 🧪 Написание тестов

### Структура теста

```python
import pytest


class TestFeatureName:
    """Test feature description"""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly"""
        # Arrange
        input_data = "test"

        # Act
        result = function_under_test(input_data)

        # Assert
        assert result == expected_output


    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function"""
        result = await async_function()
        assert result is not None
```

### Markers

```python
@pytest.mark.unit  # Unit тест
@pytest.mark.integration  # Integration тест
@pytest.mark.slow  # Медленный тест
```

### Fixtures

Используйте fixtures из `conftest.py`:

```python
def test_with_mock_version(mock_version):
    assert mock_version == "8.3.26"
```

## 📦 Добавление зависимостей

### Production зависимости

```bash
# Добавить в requirements-base.txt
echo "new-package==1.0.0" >> requirements-base.txt

# Обновить lock файл
pip install -r requirements-base.txt
pip freeze > requirements.lock
```

### Dev зависимости

```bash
# Добавить в requirements-dev.txt
echo "new-dev-package==1.0.0" >> requirements-dev.txt
pip install -r requirements-dev.txt
```

## 🔄 Git workflow

### Commit messages

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавить новую функцию
fix: исправить баг с поиском
docs: обновить README
test: добавить тесты для валидации
refactor: рефакторинг парсера HBK
perf: оптимизировать индексацию
chore: обновить зависимости
```

### Branches

```bash
# Создание feature branch
git checkout -b feature/my-feature

# Создание bugfix branch
git checkout -b fix/bug-description
```

### Pull Request

1. Создайте branch из `main`
2. Внесите изменения
3. Убедитесь что тесты проходят
4. Убедитесь что pre-commit hooks проходят
5. Создайте PR в GitHub
6. Дождитесь review

## 🐛 Отладка

### Локальный запуск

```bash
# Без Docker
python src/server.py

# С Docker
docker compose up
```

### Логирование

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Изменение уровня логирования

```bash
# В .env
LOG_LEVEL=DEBUG
```

## 📚 Дополнительные ресурсы

- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
