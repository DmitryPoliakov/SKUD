FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY . .

# Создаем директории для данных
RUN mkdir -p data/reports && \
    mkdir -p static && \
    mkdir -p templates

# Устанавливаем переменные окружения
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Открываем порт
EXPOSE 5000

# Создаем non-root пользователя
RUN useradd -r -s /bin/bash skud && \
    chown -R skud:skud /app

USER skud

# Команда запуска
CMD ["python", "run.py"] 