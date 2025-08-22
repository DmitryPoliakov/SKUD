# 🚀 Установка СКУД бота на Linux сервер

## Команды для выполнения на сервере:

### 1. Подготовка системы
```bash
# Переходим в директорию проекта
cd /home/SKUD_iogram

# Обновляем систему и устанавливаем Python
apt update
apt install -y python3 python3-pip python3-venv

# Создаем виртуальное окружение
python3 -m venv venv

# Активируем виртуальное окружение
source venv/bin/activate
```

### 2. Установка зависимостей
```bash
# Обновляем pip
pip install --upgrade pip

# Устанавливаем основные зависимости
pip install aiogram==3.13.1
pip install requests

# Дополнительные зависимости (опционально)
pip install pandas matplotlib seaborn xlsxwriter python-dotenv
```

### 3. Создание данных
```bash
# Создаем директории
mkdir -p data/reports

# Если нет файла сотрудников, создаем его
cat > data/employees.json << 'EOF'
{
    "992BEE97": "Поляков Павел",
    "894046B8": "Тарасов Никита", 
    "92C2001D": "Поляков Дмитрий",
    "E9DBA5A3": "Шура",
    "296DD1A3": "Пущинский Марк",
    "97D3A7DD": "Палкин Семён"
}
EOF

# Если нет файла посещаемости, создаем его
cat > data/attendance.csv << 'EOF'
date,employee,arrival,departure
2025-01-08,Поляков Павел,09:15,17:30
2025-01-08,Тарасов Никита,08:45,18:00
EOF
```

### 4. Обновление токена (ВАЖНО!)
```bash
# Отредактируйте config.py или bot_simple.py
nano config.py
# Замените тестовый токен на ваш продакшн токен
```

### 5. Запуск бота
```bash
# Простой запуск для тестирования
source venv/bin/activate
python bot_simple.py

# Оптимизированная версия для продакшена
python start_optimized.py

# Или полная версия (может нагружать CPU)
python bot.py
```

### 6. Настройка автозапуска (systemd service)
```bash
# Копируем service файлы (они уже есть в проекте)
cp skud-web.service /etc/systemd/system/
cp skud-bot.service /etc/systemd/system/

# Перезагружаем systemd
systemctl daemon-reload

# Включаем автозапуск обеих служб
systemctl enable skud-web
systemctl enable skud-bot

# Запускаем службы (веб-сервер первым)
systemctl start skud-web
systemctl start skud-bot

# Проверяем статус
systemctl status skud-web
systemctl status skud-bot
```

### 7. Мониторинг
```bash
# Просмотр логов веб-сервера
journalctl -u skud-web -f

# Просмотр логов бота
journalctl -u skud-bot -f

# Просмотр обеих служб одновременно
journalctl -u skud-web -u skud-bot -f

# Остановка служб
systemctl stop skud-web skud-bot

# Перезапуск служб
systemctl restart skud-web skud-bot

# Проверка портов
netstat -tulpn | grep :5000  # Веб-сервер
```

## 🐛 Решение проблем

### ⚡ Высокая нагрузка на CPU:
```bash
# Используйте оптимизированную версию
systemctl stop skud-bot
systemctl edit skud-bot
# Измените ExecStart на start_optimized.py
systemctl restart skud-bot

# Проверьте ресурсы
systemctl status skud-bot
journalctl -u skud-bot --since "1 hour ago"
```

### 📱 Уведомления не приходят:
```bash
# Проверьте конфигурацию
python -c "from config import config; print(f'Token: {bool(config.TELEGRAM_TOKEN)}, Admin: {config.ADMIN_USER_ID}')"

# Проверьте логи веб-сервера
journalctl -u skud-web -f

# Проверьте логи бота
journalctl -u skud-bot -f

# Тест уведомлений через веб-сервер
curl -X POST http://localhost:5000/api/attendance \
  -H "Content-Type: application/json" \
  -d '{"serial": "TEST123", "time": "2025-01-08 12:00:00"}'
```

### 🌐 Веб-интерфейс не работает:
```bash
# Проверка веб-сервера
systemctl status skud-web
journalctl -u skud-web --since "1 hour ago"

# Проверка доступности
curl http://localhost:5000/api/health

# Проверка порта
netstat -tulpn | grep :5000
```

### 📱 Telegram WebApp не работает:
```bash
# Убедитесь что веб-сервер доступен по HTTPS
curl https://skud-ek.ru/telegram-reports

# Проверьте настройки домена
# WebApp работает только с HTTPS доменами
```

### Если aiogram не установился:
```bash
# Попробуйте другую версию
pip install aiogram==3.10.0

# Или установите через apt
apt install python3-aiogram
```

### Если проблемы с pandas/matplotlib:
```bash
# Установите системные зависимости
apt install python3-pandas python3-matplotlib python3-seaborn

# Или используйте bot_simple.py без этих зависимостей
```

### Проверка работы бота:
```bash
# Проверяем, что процесс запущен
ps aux | grep bot

# Проверяем сетевые соединения
netstat -tulpn | grep python

# Тест импорта
python -c "import aiogram; print('OK')"

# Проверка памяти
free -h
top -p $(pgrep -f "python.*bot")
```

## ✅ Готово!

После выполнения этих команд будут работать две службы:

**🌐 skud-web** - веб-сервер на порту 5000:
- Веб-интерфейс на skud-ek.ru
- API для ESP32 (/api/attendance)  
- Telegram WebApp интеграция (/telegram-reports)
- Генерация отчетов

**🤖 skud-bot** - Telegram бот:
- Команды в Telegram чате
- Уведомления о событиях СКУД
- WebApp интеграция
- Генерация отчетов через бот

Обе службы автоматически запускаются при перезагрузке сервера.
