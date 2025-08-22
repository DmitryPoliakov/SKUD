# СКУД Telegram Бот на aiogram

Копия системы контроля и учета доступа (СКУД) с Telegram ботом на библиотеке aiogram для тестирования.

## Особенности

- **Современная библиотека**: Использует aiogram 3.x вместо python-telegram-bot
- **Тестовый токен**: Настроен с тестовым токеном для локальной отладки
- **Полная совместимость**: Все функции оригинального бота сохранены
- **Готов к деплою**: Легко переносится на облачный Linux сервер

## Быстрый старт

### Windows
```cmd
start.bat
```

### Linux/Mac
```bash
python3 run.py
```

## Возможности бота

### Команды
- `/start` - главное меню с кнопками
- `/report` - генерация отчетов за месяц
- `/diagnose` - диагностика данных
- `/check_data` - проверка данных в реальном времени
- `/add_employee` - добавление нового сотрудника
- `/webapp` - открытие Web App для отчетов

### Функции
- 📊 **Генерация отчетов** - Excel файлы с детальной статистикой
- 📈 **Графики** - визуализация отработанных часов
- 🔍 **Диагностика** - проверка состояния данных
- 🌐 **Web App** - удобный интерфейс в Telegram
- 👥 **Управление сотрудниками** - добавление через бота
- 📱 **Inline кнопки** - современный интерфейс

## Конфигурация

### Тестовые настройки
```python
TELEGRAM_TOKEN = "8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM"
ALLOWED_USERS = []  # Пустой список = доступ для всех
WEBAPP_URL = "http://localhost:5000/telegram-reports?tgWebApp=1"
```

### Для продакшена
Отредактируйте `config.py`:
```python
TELEGRAM_TOKEN = "ваш_реальный_токен"
ALLOWED_USERS = [ваш_user_id, другой_user_id]
ADMIN_USER_ID = ваш_admin_id
WEBAPP_URL = "https://ваш_домен.ru/telegram-reports?tgWebApp=1"
```

## Структура проекта

```
SKUD_iogram/
├── bot.py              # Основной файл бота на aiogram
├── config.py           # Конфигурация
├── utils/
│   ├── __init__.py
│   └── data_manager.py # Работа с данными (CSV, Excel, графики)
├── data/               # Данные (создается автоматически)
│   ├── attendance.csv  # Данные посещаемости
│   ├── employees.json  # Список сотрудников
│   └── reports/        # Сгенерированные отчеты
├── requirements.txt    # Зависимости Python
├── run.py             # Скрипт запуска
├── start.bat          # Batch файл для Windows
└── README.md          # Документация
```

## Зависимости

- **aiogram 3.13.1** - современная библиотека для Telegram ботов
- **pandas** - обработка данных
- **matplotlib/seaborn** - создание графиков
- **xlsxwriter** - генерация Excel файлов

## Миграция с python-telegram-bot

### Основные изменения
1. **Async/await** - весь код асинхронный
2. **Фильтры** - новая система фильтров `F.data.startswith()`
3. **Типы сообщений** - `BufferedInputFile` вместо `InputFile`
4. **Состояния** - FSM через `aiogram.fsm`
5. **Callback Query** - упрощенная обработка

### Преимущества aiogram
- ⚡ **Лучшая производительность** - полностью асинхронный
- 🔧 **Современный API** - актуальные Telegram функции
- 📱 **Web Apps** - лучшая поддержка веб-приложений
- 🎯 **Типизация** - полная поддержка type hints
- 🧩 **Middleware** - гибкая система промежуточного ПО

## Тестирование

1. Запустите бота локально
2. Найдите бота в Telegram по токену
3. Отправьте `/start`
4. Протестируйте все команды

## Деплой на сервер

### 1. Скопируйте файлы
```bash
scp -r SKUD_iogram/ user@server:/path/to/bot/
```

### 2. Установите зависимости
```bash
pip3 install -r requirements.txt
```

### 3. Настройте systemd service
```bash
sudo nano /etc/systemd/system/skud-bot.service
```

```ini
[Unit]
Description=SKUD Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bot/SKUD_iogram
ExecStart=/usr/bin/python3 run.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Запустите службу
```bash
sudo systemctl enable skud-bot
sudo systemctl start skud-bot
```

## Логирование

Логи сохраняются в файл `telegram_bot.log` в директории бота.

Для просмотра логов в реальном времени:
```bash
tail -f telegram_bot.log
```

## Поддержка

При возникновении проблем:
1. Проверьте логи в `telegram_bot.log`
2. Убедитесь, что токен действителен
3. Проверьте доступ к файлам данных
4. Используйте команду `/diagnose` для диагностики

## Лицензия

MIT License - аналогично оригинальному проекту.
