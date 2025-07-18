# СКУД - Система контроля и учета доступа на Python

Система контроля и учета доступа (СКУД) с использованием ESP32 и RFID-считывателя RC522, с серверной частью на Python и телеграм-ботом для отчетов.

## Структура проекта

```
SKUD_Python/
├── app/                        # Директория с приложением
│   ├── __init__.py            # Инициализация пакета Python
│   ├── main.py                # Flask API и веб-интерфейс
│   ├── telegram_bot.py        # Телеграм-бот для отчетов и уведомлений
│   ├── auto_close.py          # Автоматическое закрытие незавершенных дней
│   ├── db.py                  # Функции для работы с базой данных
│   └── web_routes.py          # Дополнительные веб-маршруты
├── data/                       # Директория для хранения данных
│   ├── attendance.csv         # Файл с данными посещаемости
│   ├── employees.json         # Файл со списком сотрудников
│   └── reports/               # Директория для сгенерированных отчетов
├── templates/                  # HTML шаблоны для веб-интерфейса
│   ├── base.html              # Базовый шаблон
│   ├── dashboard.html         # Панель управления
│   ├── attendance.html        # Страница посещаемости
│   ├── employees.html         # Управление сотрудниками
│   └── reports.html           # Страница отчетов
├── static/                     # Статические файлы
│   ├── css/style.css          # Стили
│   └── js/                    # JavaScript файлы
├── RFID_RC522_Tracker_Python/ # Arduino скетч для ESP32
│   └── RFID_RC522_Tracker_Python.ino
├── requirements.txt           # Зависимости Python
├── run.py                     # Скрипт для запуска всех компонентов
├── start.bat                  # Batch файл для запуска в Windows
├── ARCHITECTURE.md            # Архитектура системы
├── SETUP.md                   # Инструкции по настройке
└── README.md                  # Документация проекта
```

## Возможности системы

### Основные функции
- **Учет посещаемости**: автоматическая регистрация прихода и ухода сотрудников по RFID-картам
- **Веб-интерфейс**: панель управления с дашбордом, просмотром посещаемости и управлением сотрудниками
- **Телеграм-бот**: удобный интерфейс для получения отчетов и уведомлений
- **Автоматические отчеты**: генерация Excel-файлов с детальной статистикой
- **Визуализация данных**: графики посещаемости и отработанных часов
- **Автоматическое закрытие дней**: система закрывает незавершенные дни в 00:01

### Логика определения прихода/ухода
Система определяет тип события на основе существующих записей за день:

1. **Первое сканирование карты в день** → **ПРИХОД**
2. **Второе сканирование** → **УХОД**  
3. **Последующие сканирования** → **Перезапись времени ухода**

**Пример:**
```
09:00 - Иванов сканирует карту → ПРИХОД
17:30 - Иванов сканирует карту → УХОД
18:00 - Иванов сканирует карту → УХОД (обновление времени)
```

## Установка и настройка

### Требования
- Python 3.8 или выше
- ESP32 с подключенным RFID-считывателем RC522
- Доступ к Telegram API (для создания бота)

### Установка зависимостей
```bash
pip install -r requirements.txt
```

### Настройка ESP32

1. Откройте файл `RFID_RC522_Tracker_Python/RFID_RC522_Tracker_Python.ino` в Arduino IDE
2. Установите необходимые библиотеки:
   - WiFi
   - HTTPClient
   - ArduinoJson
   - MFRC522
3. Настройте параметры подключения:
   ```cpp
   const char* primary_ssid = "ваш_ssid";
   const char* primary_password = "ваш_пароль";
   const char* serverURL = "http://ваш_ip:5000/api/attendance";
   ```
4. Загрузите скетч в ESP32

### Схема подключения RC522 к ESP32-C3
```
+-----------+----------------+
| RC522     | ESP32-C3       |
+-----------+----------------+
| SDA (SS)  | GPIO6 (D4)     |
| SCK       | GPIO8 (D8)     |
| MOSI      | GPIO10 (D10)   |
| MISO      | GPIO9 (D9)     |
| GND       | GND            |
| RST       | GPIO7 (D5)     |
| 3.3V      | 3V3            |
+-----------+----------------+
```

### Настройка телеграм-бота

1. Создайте бота через @BotFather в Telegram
2. Получите токен бота
3. Откройте файл `app/telegram_bot.py` и настройте:
   ```python
   TELEGRAM_TOKEN = "ваш_токен_бота"
   ALLOWED_USERS = [ваш_user_id]  # ID пользователей с доступом
   ADMIN_USER_ID = ваш_user_id    # ID для уведомлений
   ```

## Запуск системы

### Автоматический запуск
```bash
python run.py
```
Или в Windows:
```cmd
start.bat
```

Это запустит:
- Flask API на порту 5000
- Веб-интерфейс (http://localhost:5000)
- Телеграм-бота
- Планировщик для автоматического закрытия дней

### Ручной запуск компонентов
```bash
# Только веб-сервер
python -m app.main

# Только телеграм-бот
python app/telegram_bot.py

# Только автозакрытие дней
python app/auto_close.py
```

## Использование

### Веб-интерфейс
1. Откройте http://localhost:5000 в браузере
2. **Панель управления** - статистика и графики
3. **Посещаемость** - просмотр записей с фильтрами
4. **Сотрудники** - управление списком сотрудников
5. **Отчеты** - генерация и скачивание отчетов

### Телеграм-бот
1. Найдите своего бота в Telegram
2. Отправьте `/start` для начала работы
3. Доступные команды:
   - `/report` - получить отчет за месяц
   - `/add_employee <серийный_номер> <имя>` - добавить сотрудника
   - `/webapp` - открыть веб-приложение

### API endpoints
- `POST /api/attendance` - регистрация посещения от ESP32
- `GET /api/health` - проверка работоспособности
- `GET /dashboard` - панель управления
- `GET /attendance` - страница посещаемости
- `GET /employees` - управление сотрудниками
- `GET /reports` - страница отчетов

## Формат данных

### attendance.csv
```csv
date,employee,arrival,departure
2025-07-06,Поляков,09:15,17:30
2025-07-06,Тарасов,08:45,18:00
2025-07-07,Поляков,09:05,
```

### employees.json
```json
{
  "992BEE97": "Поляков",
  "894046B8": "Тарасов",
  "E9DBA5A3": "Шура"
}
```

## Автоматическое закрытие дней

Система автоматически закрывает незавершенные дни (записи с приходом, но без ухода) в 00:01 следующего дня, устанавливая время ухода по умолчанию (17:00).

## Уведомления

Система отправляет уведомления администратору через Telegram:
- При каждом сканировании карты
- При обнаружении неизвестной карты
- При ошибках в работе системы

## Безопасность

- Контроль доступа к телеграм-боту по ID пользователей
- Локальное хранение данных
- Логирование всех операций
- Защита от неизвестных карт

## Технические детали

### Зависимости
- **flask** - веб-фреймворк
- **pandas** - обработка данных
- **python-telegram-bot** - телеграм-бот
- **matplotlib, seaborn** - графики
- **xlsxwriter** - генерация Excel
- **schedule** - планировщик задач

### Логирование
Система ведет логи в файлы:
- `app.log` - основные события
- `telegram_bot.log` - события бота
- `auto_close.log` - автозакрытие дней
- `skud.log` - общий лог системы

## Устранение неполадок

### Частые проблемы
1. **ESP32 не подключается к WiFi** - проверьте настройки сети
2. **Карты не распознаются** - проверьте подключение RC522
3. **Бот не отвечает** - проверьте токен и права доступа
4. **Веб-интерфейс недоступен** - проверьте порт 5000

### Отладка
- Включите режим отладки в `main.py`: `debug=True`
- Проверьте логи в соответствующих файлах
- Используйте `/api/health` для проверки API

## Лицензия

MIT License
