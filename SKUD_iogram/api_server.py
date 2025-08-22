#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import pandas as pd
from datetime import datetime
from flask import Flask, request, jsonify
import logging
from logging.handlers import RotatingFileHandler

# Создаем экземпляр Flask
app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('api.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Настройки путей (относительно рабочей директории)
DATA_DIR = 'data'
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.csv')
EMPLOYEES_FILE = os.path.join(DATA_DIR, 'employees.json')

# Убедимся, что директория для данных существует
os.makedirs(DATA_DIR, exist_ok=True)

def load_employees():
    """Загружает список сотрудников из JSON файла"""
    try:
        if os.path.exists(EMPLOYEES_FILE):
            with open(EMPLOYEES_FILE, 'r', encoding='utf-8') as f:
                employees = json.load(f)
                logger.info(f"Загружено {len(employees)} сотрудников")
                return employees
        else:
            logger.warning(f"Файл сотрудников {EMPLOYEES_FILE} не найден")
            return {}
    except Exception as e:
        logger.error(f"Ошибка при загрузке сотрудников: {str(e)}")
        return {}

def load_attendance_data():
    """Загружает данные посещаемости из CSV файла"""
    try:
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            logger.info(f"Загружено {len(df)} записей посещаемости")
            return df
        else:
            logger.warning(f"Файл посещаемости {ATTENDANCE_FILE} не найден, создаем новый")
            df = pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])
            return df
    except Exception as e:
        logger.error(f"Ошибка при загрузке данных посещаемости: {str(e)}")
        return pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])

def save_attendance_data(df):
    """Сохраняет данные посещаемости в CSV файл"""
    try:
        df.to_csv(ATTENDANCE_FILE, index=False)
        logger.info(f"Данные посещаемости сохранены: {len(df)} записей")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных посещаемости: {str(e)}")

def save_new_employee(serial, name):
    """Добавляет нового сотрудника в список"""
    try:
        employees = load_employees()
        employees[serial] = name
        with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
            json.dump(employees, f, ensure_ascii=False, indent=4)
        logger.info(f"Добавлен новый сотрудник: {name} ({serial})")
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")
        return False

def notify_telegram_bot(message):
    """Отправляет уведомление через Telegram Bot HTTP API"""
    try:
        import requests
        
        # Токен и ID администратора из конфигурации
        BOT_TOKEN = "7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY"
        ADMIN_USER_ID = 42291783
        
        # URL для отправки сообщения через Telegram Bot API
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # Данные для отправки
        data = {
            'chat_id': ADMIN_USER_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        # Отправляем HTTP запрос
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Уведомление успешно отправлено администратору: {message}")
        else:
            logger.error(f"Ошибка отправки уведомления: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {str(e)}")


def load_employee_telegram_ids():
    """Загружает связь сотрудников с их Telegram ID"""
    try:
        employee_telegram_file = os.path.join(DATA_DIR, 'employee_telegram.json')
        if os.path.exists(employee_telegram_file):
            with open(employee_telegram_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем файл с примером структуры
            default_mapping = {
                "Поляков Павел": None,
                "Тарасов Никита": None,
                "Поляков Дмитрий": None,
                "Шура": None,
                "Пущинский Марк": None,
                "Палкин Семён": None
            }
            with open(employee_telegram_file, 'w', encoding='utf-8') as f:
                json.dump(default_mapping, f, ensure_ascii=False, indent=4)
            logger.info(f"Создан файл связи сотрудников с Telegram: {employee_telegram_file}")
            return default_mapping
    except Exception as e:
        logger.error(f"Ошибка при загрузке связи сотрудников с Telegram: {str(e)}")
        return {}

def send_employee_notification(employee_name, event_type, time_str, date_str, serial):
    """Отправляет уведомление сотруднику о его приходе/уходе"""
    try:
        employee_telegram_ids = load_employee_telegram_ids()
        employee_telegram_id = employee_telegram_ids.get(employee_name)
        
        if not employee_telegram_id:
            logger.info(f"Telegram ID для сотрудника {employee_name} не настроен, уведомление не отправлено")
            return
        
        import requests
        
        # Токен бота
        BOT_TOKEN = "7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY"
        
        # URL для отправки сообщения
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # Эмодзи в зависимости от типа события
        emoji = "🟢" if event_type == "приход" else "🔴"
        
        # Текст сообщения для сотрудника
        message_text = f"{emoji} Добро пожаловать!\n\n" \
                      f"📅 Ваш {event_type} зафиксирован в {time_str}\n" \
                      f"📆 Дата: {date_str}\n" \
                      f"🏷️ Карта: {serial}\n\n" \
                      f"Хорошего рабочего дня! 😊"
        
        if event_type == "уход":
            message_text = f"{emoji} До свидания!\n\n" \
                          f"📅 Ваш {event_type} зафиксирован в {time_str}\n" \
                          f"📆 Дата: {date_str}\n" \
                          f"🏷️ Карта: {serial}\n\n" \
                          f"Увидимся завтра! 👋"
        
        # Данные для отправки
        data = {
            'chat_id': employee_telegram_id,
            'text': message_text,
            'parse_mode': 'HTML'
        }
        
        # Отправляем HTTP запрос
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Уведомление отправлено сотруднику {employee_name} (ID: {employee_telegram_id}): {event_type}")
        else:
            logger.error(f"Ошибка отправки уведомления сотруднику {employee_name}: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления сотруднику {employee_name}: {str(e)}")

# Маршрут для обработки запросов от ESP32
@app.route('/api/attendance', methods=['POST'])
def record_attendance():
    """Основной API эндпоинт для записи данных от ESP32"""
    try:
        data = request.json
        logger.info(f"Получены данные от ESP32: {data}")
        
        # Проверяем формат данных
        if not data or 'serial' not in data or 'time' not in data:
            logger.error("Неверный формат данных от ESP32")
            return jsonify({
                'status': 'error',
                'message': 'Неверный формат данных'
            }), 400
        
        serial = data['serial'].upper()
        timestamp = data['time']
        
        # Загружаем список сотрудников
        employees = load_employees()
        
        # Проверяем, есть ли сотрудник с таким серийным номером
        if serial not in employees:
            logger.warning(f"Неизвестный серийный номер: {serial}")
            
            # Отправляем уведомление о неизвестной карте
            unknown_card_message = f"СКУД: Обнаружена неизвестная карта: {serial}\\n\\n" \
                                  f"Для добавления сотрудника отправьте команду:\\n" \
                                  f"/add_employee {serial} Имя_Сотрудника"
            notify_telegram_bot(unknown_card_message)
            
            return jsonify({
                'status': 'unknown',
                'message': f'Неизвестный ключ: {serial}'
            }), 404
        
        employee_name = employees[serial]
        logger.info(f"Обработка события для сотрудника: {employee_name}")
        
        # Парсим дату и время
        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M')
        
        # Загружаем данные посещаемости
        df = load_attendance_data()
        
        # Ищем запись для этого сотрудника и даты
        mask = (df['date'] == date_str) & (df['employee'] == employee_name)
        
        if mask.any():
            # Запись уже существует
            row = df.loc[mask].iloc[0]
            idx = df.loc[mask].index[0]
            
            if pd.isna(row['arrival']) or row['arrival'] == '':
                # Записываем приход
                df.at[idx, 'arrival'] = time_str
                event_type = 'приход'
            elif pd.isna(row['departure']) or row['departure'] == '':
                # Записываем уход
                df.at[idx, 'departure'] = time_str
                event_type = 'уход'
            else:
                # Обновляем уход (повторное сканирование)
                df.at[idx, 'departure'] = time_str
                event_type = 'уход (обновлено)'
        else:
            # Создаем новую запись (первое сканирование = приход)
            new_row = {
                'date': date_str,
                'employee': employee_name,
                'arrival': time_str,
                'departure': ''
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            event_type = 'приход'
        
        # Сохраняем обновленные данные
        save_attendance_data(df)
        
        logger.info(f"Записано событие: {event_type} для {employee_name} в {time_str} ({date_str})")
        
        # Отправляем простое уведомление администратору
        notification_message = f"СКУД: {employee_name}: {event_type} в {time_str} ({date_str})"
        notify_telegram_bot(notification_message)
        
        # Отправляем уведомление сотруднику
        send_employee_notification(employee_name, event_type, time_str, date_str, serial)
        
        # Возвращаем ответ ESP32
        return jsonify({
            'status': 'success',
            'message': 'Данные успешно записаны',
            'employee': employee_name,
            'event': event_type,
            'time': time_str,
            'date': date_str
        })
        
    except ValueError as e:
        logger.error(f"Ошибка парсинга данных: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Ошибка формата времени: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.exception(f"Ошибка при обработке запроса от ESP32: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Внутренняя ошибка сервера: {str(e)}'
        }), 500

# API для проверки работоспособности
@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности API"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'API СКУД работает нормально',
        'version': '2.0 (aiogram)',
        'data_files': {
            'attendance': os.path.exists(ATTENDANCE_FILE),
            'employees': os.path.exists(EMPLOYEES_FILE)
        }
    })

# API для получения статистики
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Получение статистики посещаемости"""
    try:
        df = load_attendance_data()
        employees = load_employees()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Записи за сегодня
        today_records = df[df['date'] == today]
        
        # Присутствующие (есть приход, нет ухода)
        present_count = len(today_records[
            (today_records['arrival'].notna()) & 
            (today_records['arrival'] != '') & 
            ((today_records['departure'].isna()) | (today_records['departure'] == ''))
        ])
        
        return jsonify({
            'today_present': present_count,
            'total_employees': len(employees),
            'total_records': len(df),
            'today_records': len(today_records),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {str(e)}")
        return jsonify({
            'error': 'Ошибка при получении статистики',
            'timestamp': datetime.now().isoformat()
        }), 500

# API для добавления сотрудника (вызывается ботом)
@app.route('/api/add_employee', methods=['POST'])
def add_employee_api():
    """API для добавления сотрудника через бот"""
    try:
        data = request.json
        if not data or 'serial' not in data or 'name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Требуются поля serial и name'
            }), 400
        
        serial = data['serial'].upper()
        name = data['name']
        
        # Проверяем, не существует ли уже
        employees = load_employees()
        if serial in employees:
            return jsonify({
                'status': 'error',
                'message': f'Сотрудник с картой {serial} уже существует'
            }), 409
        
        # Добавляем сотрудника
        if save_new_employee(serial, name):
            logger.info(f"Через API добавлен сотрудник: {name} ({serial})")
            return jsonify({
                'status': 'success',
                'message': f'Сотрудник {name} с картой {serial} успешно добавлен'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Ошибка при сохранении сотрудника'
            }), 500
            
    except Exception as e:
        logger.error(f"Ошибка при добавлении сотрудника через API: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Внутренняя ошибка: {str(e)}'
        }), 500

if __name__ == '__main__':
    logger.info("Запуск API сервера СКУД (новая версия)")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    logger.info(f"Файл посещаемости: {ATTENDANCE_FILE}")
    logger.info(f"Файл сотрудников: {EMPLOYEES_FILE}")
    
    # Запускаем сервер на порту 5001 (чтобы не конфликтовать со старым)
    app.run(host='0.0.0.0', port=5001, debug=False)
