#!/bin/bash

# Простой скрипт запуска бота в виртуальном окружении

echo "🤖 Запуск СКУД бота"
echo "=================="

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено!"
    echo "Запустите сначала: bash setup_server.sh"
    exit 1
fi

# Активируем виртуальное окружение
echo "⚡ Активация виртуального окружения..."
source venv/bin/activate

# Проверяем наличие aiogram
python -c "import aiogram; print('✅ aiogram найден')" 2>/dev/null || {
    echo "❌ aiogram не установлен!"
    echo "Установка aiogram..."
    pip install aiogram==3.13.1
}

# Запускаем бота
echo "🚀 Запуск бота..."
if [ -f "bot_simple.py" ]; then
    python bot_simple.py
elif [ -f "bot.py" ]; then
    python bot.py
else
    echo "❌ Файл бота не найден!"
    exit 1
fi
