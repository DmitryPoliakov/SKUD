#!/bin/bash

# Скрипт настройки СКУД бота на Linux сервере

echo "🚀 Настройка СКУД бота на Linux сервере"
echo "========================================"

# Проверяем, что мы в правильной директории
if [ ! -f "bot.py" ]; then
    echo "❌ Ошибка: файл bot.py не найден в текущей директории"
    echo "Убедитесь, что вы находитесь в папке SKUD_iogram"
    exit 1
fi

# 1. Обновляем систему и устанавливаем Python и pip
echo "📦 Обновление системы и установка зависимостей..."
apt update
apt install -y python3 python3-pip python3-venv

# 2. Создаем виртуальное окружение
echo "🔧 Создание виртуального окружения..."
python3 -m venv venv

# 3. Активируем виртуальное окружение
echo "⚡ Активация виртуального окружения..."
source venv/bin/activate

# 4. Устанавливаем зависимости
echo "📚 Установка Python зависимостей..."
pip install --upgrade pip
pip install aiogram==3.13.1
pip install requests

# Пытаемся установить дополнительные зависимости (могут потребовать компиляции)
echo "📊 Попытка установки дополнительных зависимостей..."
pip install pandas matplotlib seaborn xlsxwriter python-dotenv || echo "⚠️ Некоторые зависимости не установлены (не критично для базовой работы)"

# 5. Создаем директории данных
echo "📁 Создание директорий..."
mkdir -p data/reports
mkdir -p logs

# 6. Создаем тестовые данные если их нет
if [ ! -f "data/employees.json" ]; then
    echo "👥 Создание тестового файла сотрудников..."
    cat > data/employees.json << 'EOF'
{
    "992BEE97": "Поляков Павел",
    "894046B8": "Тарасов Никита",
    "92C2001D": "Поляков Дмитрий",
    "E9DBA5A3": "Шура",
    "32AABBD6": "Поляков Павел",
    "296DD1A3": "Пущинский Марк",
    "97D3A7DD": "Палкин Семён"
}
EOF
fi

if [ ! -f "data/attendance.csv" ]; then
    echo "📊 Создание тестового файла посещаемости..."
    cat > data/attendance.csv << 'EOF'
date,employee,arrival,departure
2025-01-08,Поляков Павел,09:15,17:30
2025-01-08,Тарасов Никита,08:45,18:00
2025-01-08,Шура,10:00,16:45
2025-01-09,Поляков Павел,09:05,17:15
2025-01-09,Тарасов Никита,08:50,17:45
2025-01-09,Пущинский Марк,09:30,18:30
EOF
fi

# 7. Создаем systemd service файл
echo "🔧 Создание systemd service..."
cat > /etc/systemd/system/skud-bot.service << EOF
[Unit]
Description=SKUD Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/SKUD_iogram
Environment=PATH=/home/SKUD_iogram/venv/bin
ExecStart=/home/SKUD_iogram/venv/bin/python bot_simple.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. Перезагружаем systemd
systemctl daemon-reload

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "🚀 Для запуска бота выполните:"
echo "   source venv/bin/activate"
echo "   python bot_simple.py"
echo ""
echo "🔧 Для автозапуска как службы:"
echo "   systemctl enable skud-bot"
echo "   systemctl start skud-bot"
echo "   systemctl status skud-bot"
echo ""
echo "📝 Логи службы:"
echo "   journalctl -u skud-bot -f"
echo ""
echo "⚠️  ВАЖНО: Обновите токен в config.py для продакшена!"
echo ""
