# =============================================================================
# MCP сервис справки 1С
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Установка Python зависимостей
COPY requirements-base.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements-base.txt

# Копируем исходный код
COPY src/ ./src/

# Создаем директории для данных
RUN mkdir -p /app/data /app/logs

# Запуск сервера
CMD ["python", "-m", "src.server"]
