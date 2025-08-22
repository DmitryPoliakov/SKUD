#!/bin/bash

echo "🚀 Настройка новой системы СКУД с aiogram"
echo "========================================"

# 1. Копирование актуальных данных
echo ""
echo "📂 1. Копирование актуальных данных из старой системы..."
cd /home/SKUD_iogram

if [ -f "/home/SKUD/SKUD_Python/data/attendance.csv" ]; then
    cp /home/SKUD/SKUD_Python/data/attendance.csv data/attendance.csv
    echo "✅ attendance.csv скопирован"
    echo "📊 Последние записи:"
    tail -3 data/attendance.csv
else
    echo "❌ Файл attendance.csv не найден в старой системе"
    echo "📄 Создаем пустой файл..."
    echo "date,employee,arrival,departure" > data/attendance.csv
fi

if [ -f "/home/SKUD/SKUD_Python/data/employees.json" ]; then
    cp /home/SKUD/SKUD_Python/data/employees.json data/employees.json
    echo "✅ employees.json скопирован"
    echo "👥 Количество сотрудников: $(cat data/employees.json | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")"
else
    echo "❌ Файл employees.json не найден в старой системе"
    echo "📄 Создаем пустой файл..."
    echo "{}" > data/employees.json
fi

# 2. Установка Flask если нет
echo ""
echo "📦 2. Установка дополнительных зависимостей..."
source venv/bin/activate
pip install flask==2.3.3
echo "✅ Flask установлен"

# 3. Создание systemd service для API
echo ""
echo "🔧 3. Создание службы API сервера..."
cp skud-api.service /etc/systemd/system/
systemctl daemon-reload
echo "✅ Служба API создана"

# 4. Настройка Nginx для перенаправления API на новый сервер
echo ""
echo "🌐 4. Перенастройка Nginx для нового API..."

# Создаем бэкап текущей конфигурации
cp /etc/nginx/sites-available/skud /etc/nginx/sites-available/skud.backup
echo "💾 Создан бэкап: skud.backup"

# Изменяем существующую конфигурацию skud
cat > /etc/nginx/sites-available/skud << 'EOF'
server {
    listen 80;
    server_name 194.87.43.42;

    # API эндпоинты теперь идут на новый сервер
    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Веб-интерфейс остается на старом сервере
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /home/SKUD/SKUD_Python/static;
    }
}
EOF

# Проверяем и перезагружаем Nginx
nginx -t
if [ $? -eq 0 ]; then
    systemctl reload nginx
    echo "✅ Nginx перенастроен: API → новый сервер, веб → старый"
else
    echo "❌ Ошибка конфигурации Nginx, восстанавливаем бэкап"
    cp /etc/nginx/sites-available/skud.backup /etc/nginx/sites-available/skud
    systemctl reload nginx
    exit 1
fi

# 5. Запуск служб
echo ""
echo "🚀 5. Запуск новых служб..."

# Запускаем API сервер
systemctl enable skud-api
systemctl start skud-api
sleep 3

if systemctl is-active --quiet skud-api; then
    echo "✅ API сервер запущен успешно"
else
    echo "❌ Ошибка запуска API сервера"
    systemctl status skud-api
fi

# Перезапускаем бот с новыми настройками
systemctl restart skud-bot
sleep 3

if systemctl is-active --quiet skud-bot; then
    echo "✅ Telegram бот перезапущен успешно"
else
    echo "❌ Ошибка перезапуска Telegram бота"
    systemctl status skud-bot
fi

# 6. Проверка работоспособности
echo ""
echo "🔍 6. Проверка работоспособности..."

# Проверяем API
echo "📡 Проверка API сервера:"
if curl -s http://localhost:5001/api/health > /dev/null; then
    echo "✅ API сервер отвечает на порту 5001"
    echo "📊 Статус API:"
    curl -s http://localhost:5001/api/health | python3 -m json.tool
else
    echo "❌ API сервер не отвечает"
fi

# Проверяем службы
echo ""
echo "🔧 Статус служб:"
echo "  API сервер: $(systemctl is-active skud-api)"
echo "  Telegram бот: $(systemctl is-active skud-bot)"
echo "  Nginx: $(systemctl is-active nginx)"

# Показываем порты
echo ""
echo "🌐 Сетевые порты:"
ss -tulpn | grep ":500[01]" || echo "Порты 5000-5001 не заняты"

# 7. Результат настройки
echo ""
echo "📋 РЕЗУЛЬТАТ НАСТРОЙКИ:"
echo "======================================"
echo ""
echo "✅ ESP32 НЕ НУЖНО ПЕРЕНАСТРАИВАТЬ!"
echo "   URL остается тот же: http://194.87.43.42/api/attendance"
echo "   Nginx теперь перенаправляет запросы на новый API"
echo ""
echo "🔄 Как это работает:"
echo "   ESP32 → Nginx:80 → API:5001 → SKUD_iogram/data/ → Telegram"
echo ""
echo "🧪 Для тестирования:"
echo "   curl -X POST http://194.87.43.42/api/attendance \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"serial\":\"TEST123\",\"time\":\"$(date '+%Y-%m-%d %H:%M:%S')\"}'"
echo ""
echo "🌐 Доступ к системе:"
echo "   - Веб-интерфейс: http://194.87.43.42/ (старая система)"
echo "   - API для ESP32: http://194.87.43.42/api/ (новая система)"
echo "   - Отчеты Telegram: новый бот с актуальными данными"

echo ""
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА!"
echo ""
echo "📝 Что дальше:"
echo "   1. Проверьте логи: journalctl -u skud-api -f"
echo "   2. Проверьте логи бота: journalctl -u skud-bot -f"
echo "   3. Настройте ESP32 на новый URL"
echo "   4. Протестируйте работу системы"
echo ""
echo "🔍 Файлы логов:"
echo "   API: /home/SKUD_iogram/api.log"
echo "   Bot: /home/SKUD_iogram/telegram_bot.log"
