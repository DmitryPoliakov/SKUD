#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Веб-сервер СКУД на основе оригинального main.py
Адаптирован под структуру SKUD_iogram
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, flash
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import calendar
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI

# Импортируем наши модули
from config import config
from utils.data_manager import data_manager

# Создаем экземпляр Flask
app = Flask(__name__)

# Устанавливаем секретный ключ для flash сообщений
app.secret_key = 'skud_secret_key_2025'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('web_server.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Функция для отправки уведомлений администратору
def notify_admin(message):
    """Отправляет уведомление администратору через Telegram Bot HTTP API"""
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
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")

def load_employee_telegram_ids():
    """Загружает связь сотрудников с их Telegram ID"""
    try:
        employee_telegram_file = os.path.join(config.DATA_DIR, 'employee_telegram.json')
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
    try:
        data = request.json
        logger.info(f"Получены данные: {data}")
        
        if not data or 'serial' not in data or 'time' not in data:
            logger.error("Неверный формат данных")
            return jsonify({
                'status': 'error',
                'message': 'Неверный формат данных'
            }), 400
        
        serial = data['serial'].upper()
        timestamp = data['time']
        
        # Загружаем список сотрудников
        employees = data_manager.load_employees()
        
        # Проверяем, есть ли сотрудник с таким серийным номером
        if serial not in employees:
            logger.warning(f"Неизвестный серийный номер: {serial}")
            
            # Отправляем уведомление администратору о неизвестной карте
            unknown_card_message = f"СКУД: Обнаружена неизвестная карта: {serial}\n\n" \
                                  f"Для добавления сотрудника отправьте команду:\n" \
                                  f"/add_employee {serial} Имя_Сотрудника"
            notify_admin(unknown_card_message)
            
            return jsonify({
                'status': 'unknown',
                'message': f'Неизвестный ключ: {serial}'
            }), 404
        
        employee_name = employees[serial]
        logger.info(f"Сотрудник: {employee_name}")
        
        # Парсим дату и время
        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        date_str = dt.strftime('%Y-%m-%d')
        time_str = dt.strftime('%H:%M')
        
        # Загружаем данные посещаемости
        df = data_manager.load_attendance_data()
        
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
        df.to_csv(config.ATTENDANCE_FILE, index=False)
        
        logger.info(f"Записано событие: {event_type} для {employee_name} в {time_str} ({date_str})")
        
        # Отправляем уведомление администратору
        notification_message = f"СКУД: {employee_name}: {event_type} в {time_str} ({date_str})"
        notify_admin(notification_message)
        
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
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'СКУД веб-сервер работает нормально',
        'version': '2.0 (aiogram + web)',
        'data_files': {
            'attendance': os.path.exists(config.ATTENDANCE_FILE),
            'employees': os.path.exists(config.EMPLOYEES_FILE)
        }
    })

# API для получения текущей статистики
@app.route('/api/current-stats', methods=['GET'])
def current_stats():
    try:
        # Загружаем данные посещаемости
        df = data_manager.load_attendance_data()
        
        # Текущая дата
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Загружаем список сотрудников
        employees = data_manager.load_employees()
        
        # Фильтруем записи за сегодня
        today_records = df[df['date'] == today]
        
        # Считаем присутствующих (есть приход, но нет ухода)
        today_present = len(today_records[
            (today_records['arrival'].notna()) & 
            (today_records['arrival'] != '') & 
            ((today_records['departure'].isna()) | (today_records['departure'] == ''))
        ])
        
        return jsonify({
            'today_present': today_present,
            'total_employees': len(employees),
            'total_records': len(df),
            'today_records': len(today_records),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Ошибка при получении текущей статистики: {str(e)}")
        return jsonify({
            'error': 'Ошибка при получении статистики',
            'timestamp': datetime.now().isoformat()
        }), 500

# Маршрут для главной страницы (панель управления)
@app.route('/dashboard')
@app.route('/')
def dashboard():
    try:
        # Загружаем данные посещаемости
        df = data_manager.load_attendance_data()
        
        # Текущая дата
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Загружаем список сотрудников
        employees = data_manager.load_employees()
        
        # Фильтруем записи за сегодня
        today_records = df[df['date'] == today]
        
        # Считаем присутствующих и отсутствующих
        today_present = len(today_records[
            (today_records['arrival'].notna()) & 
            (today_records['arrival'] != '') & 
            ((today_records['departure'].isna()) | (today_records['departure'] == ''))
        ])
        today_absent = len(employees) - today_present
        
        # Последние события
        recent_events = []
        for _, row in df.sort_values('date', ascending=False).head(5).iterrows():
            has_arrival = pd.notna(row['arrival']) and row['arrival'] != ''
            has_departure = pd.notna(row['departure']) and row['departure'] != ''
            
            if has_arrival and not has_departure:
                event_type = 'приход'
                time_str = row['arrival']
            elif has_departure:
                event_type = 'уход'
                time_str = row['departure']
            else:
                continue
                
            recent_events.append({
                'employee': row['employee'],
                'event_type': event_type,
                'time': time_str,
                'date': row['date']
            })
        
        # Данные для графика посещаемости за неделю
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
        weekly_labels = [(datetime.now() - timedelta(days=i)).strftime('%d.%m') for i in range(6, -1, -1)]
        weekly_data = []
        
        for date in dates:
            count = len(df[df['date'] == date])
            weekly_data.append(count)
        
        # Данные для графика среднего времени прихода
        arrival_labels = list(employees.values())
        arrival_data = []
        
        for employee in employees.values():
            employee_records = df[df['employee'] == employee]
            if not employee_records.empty:
                arrival_times = employee_records['arrival'].dropna()
                arrival_times = arrival_times[arrival_times != '']
                if len(arrival_times) > 0:
                    avg_hour = sum([int(t.split(':')[0]) + int(t.split(':')[1]) / 60 for t in arrival_times]) / len(arrival_times)
                    arrival_data.append(round(avg_hour, 2))
                else:
                    arrival_data.append(0)
            else:
                arrival_data.append(0)
        
        return render_template('dashboard.html', 
                              today_present=today_present,
                              today_absent=today_absent,
                              recent_events=recent_events,
                              weekly_labels=weekly_labels,
                              weekly_data=weekly_data,
                              arrival_labels=arrival_labels,
                              arrival_data=arrival_data)
    except Exception as e:
        logger.error(f"Ошибка при загрузке dashboard: {str(e)}")
        return f"Ошибка при загрузке панели управления: {str(e)}", 500

# Маршрут для Telegram Web App отчетов
@app.route('/telegram-reports')
@app.route('/reports')
def telegram_reports():
    try:
        # Загружаем данные посещаемости
        df = data_manager.load_attendance_data()
        
        # Текущая дата
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Загружаем список сотрудников
        employees = data_manager.load_employees()
        
        # Фильтруем записи за сегодня
        today_records = df[df['date'] == today]
        
        # Считаем присутствующих (есть приход, но нет ухода)
        today_present = len(today_records[
            (today_records['arrival'].notna()) & 
            (today_records['arrival'] != '') & 
            ((today_records['departure'].isna()) | (today_records['departure'] == ''))
        ])
        
        # Получаем список доступных лет
        available_years = []
        if not df.empty:
            available_years = sorted(df['date'].str[:4].unique().tolist())
        if not available_years:
            available_years = [str(datetime.now().year)]
        
        # Словарь месяцев на русском языке
        months = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        
        # Получаем список последних отчетов
        recent_reports = []
        try:
            for filename in os.listdir(config.REPORTS_DIR):
                if filename.endswith('.xlsx') or filename.endswith('.pdf') or filename.endswith('.csv'):
                    recent_reports.append({
                        'name': filename,
                        'filename': filename
                    })
            
            # Сортируем отчеты по времени создания (новые в начале)
            recent_reports.sort(key=lambda x: os.path.getmtime(os.path.join(config.REPORTS_DIR, x['filename'])), reverse=True)
            recent_reports = recent_reports[:5]  # Только последние 5 отчетов
        except Exception as e:
            logger.error(f"Ошибка при получении списка отчетов: {str(e)}")
        
        return render_template('telegram-reports.html',
                              available_years=available_years,
                              months=months,
                              recent_reports=recent_reports,
                              today_present=today_present,
                              total_employees=len(employees),
                              tg_webapp=True)  # Флаг для WebApp
    except Exception as e:
        logger.exception(f"Ошибка в telegram_reports: {str(e)}")
        return f"Ошибка при загрузке страницы отчетов: {str(e)}", 500

# Маршрут для генерации отчета
@app.route('/generate_report', methods=['POST'])
def generate_report():
    try:
        year = int(request.form.get('year'))
        month = int(request.form.get('month'))
        
        logger.info(f"Генерация отчета за {month}/{year}")
        
        # Генерируем отчет
        excel_file, chart_file, period = data_manager.generate_monthly_report(year, month)
        
        if excel_file is None:
            flash(f'Нет данных за {calendar.month_name[month]} {year}', 'error')
            return redirect(url_for('telegram_reports'))
        
        flash(f'Отчет за {period} успешно сгенерирован', 'success')
        return redirect(url_for('telegram_reports'))
        
    except Exception as e:
        logger.exception(f"Ошибка при генерации отчета: {str(e)}")
        flash(f'Ошибка при генерации отчета: {str(e)}', 'error')
        return redirect(url_for('telegram_reports'))

# Маршрут для скачивания отчета
@app.route('/download_report/<filename>')
def download_report(filename):
    return send_from_directory(config.REPORTS_DIR, filename, as_attachment=True)

# API для добавления сотрудника (вызывается ботом)
@app.route('/api/add_employee', methods=['POST'])
def add_employee_api():
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
        employees = data_manager.load_employees()
        if serial in employees:
            return jsonify({
                'status': 'error',
                'message': f'Сотрудник с картой {serial} уже существует'
            }), 409
        
        # Добавляем сотрудника
        if data_manager.add_employee(serial, name):
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
    logger.info("Запуск веб-сервера СКУД")
    logger.info(f"Рабочая директория: {os.getcwd()}")
    logger.info(f"Файл посещаемости: {config.ATTENDANCE_FILE}")
    logger.info(f"Файл сотрудников: {config.EMPLOYEES_FILE}")
    
    # Запускаем сервер
    app.run(host='0.0.0.0', port=5000, debug=False)
