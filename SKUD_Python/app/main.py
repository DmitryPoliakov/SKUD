#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
import pandas as pd
import os
import json
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import importlib.util
import calendar

# Создаем экземпляр Flask
template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
app = Flask(__name__, 
           template_folder=template_path,
           static_folder=static_path)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Настройки
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.csv')
EMPLOYEES_FILE = os.path.join(DATA_DIR, 'employees.json')

# Убедимся, что директория для данных существует
os.makedirs(DATA_DIR, exist_ok=True)

# Загрузка списка сотрудников
def load_employees():
    if os.path.exists(EMPLOYEES_FILE):
        with open(EMPLOYEES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Создаем файл с сотрудниками по умолчанию, если его нет
        default_employees = {
            "992BEE97": "Поляков",
            "894046B8": "Тарасов",
            "E79DF8A4": "Карта МИР 4635",
            "0A711B71": "Карта Прокатут",
            "92C2001D": "Карта МИР 0514",
            "E9DBA5A3": "Шура"
        }
        with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_employees, f, ensure_ascii=False, indent=4)
        return default_employees

# Сохранение нового сотрудника
def save_new_employee(serial, name):
    """
    Добавляет нового сотрудника в список
    
    Args:
        serial (str): Серийный номер карты
        name (str): Имя сотрудника
    """
    employees = load_employees()
    employees[serial] = name
    
    with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
        json.dump(employees, f, ensure_ascii=False, indent=4)
    
    logger.info(f"Добавлен новый сотрудник: {name} с картой {serial}")
    return True

# Загрузка данных посещаемости
def load_attendance_data():
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE)
    else:
        # Создаем пустой DataFrame, если файл не существует
        df = pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])
        df.to_csv(ATTENDANCE_FILE, index=False)
        return df

# Сохранение данных посещаемости
def save_attendance_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)
    
# Функция для отправки уведомлений администратору
def notify_admin(message):
    """
    Отправляет уведомление администратору через телеграм-бота
    
    Args:
        message (str): Текст уведомления
    """
    try:
        # Динамически импортируем модуль telegram_bot
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_bot.py')
        spec = importlib.util.spec_from_file_location("telegram_bot", module_path)
        telegram_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(telegram_bot)
        
        # Вызываем функцию для отправки уведомления
        telegram_bot.notify_admin(message)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")

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
        
        serial = data['serial']
        timestamp = data['time']
        
        # Загружаем список сотрудников
        employees = load_employees()
        
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
        df = load_attendance_data()
        
        # Ищем запись для этого сотрудника и даты
        mask = (df['date'] == date_str) & (df['employee'] == employee_name)
        
        if mask.any():
            # Запись уже существует
            row = df.loc[mask].iloc[0]
            idx = df.loc[mask].index[0]
            
            if pd.isna(row['arrival']):
                # Записываем приход
                df.at[idx, 'arrival'] = time_str
                event_type = 'приход'
            elif pd.isna(row['departure']):
                # Записываем уход
                df.at[idx, 'departure'] = time_str
                event_type = 'уход'
            else:
                # Обновляем уход
                df.at[idx, 'departure'] = time_str
                event_type = 'уход (повтор)'
        else:
            # Создаем новую запись
            new_row = {
                'date': date_str,
                'employee': employee_name,
                'arrival': time_str,
                'departure': None
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            event_type = 'приход'
        
        # Сохраняем обновленные данные
        save_attendance_data(df)
        
        logger.info(f"Записано событие: {event_type} для {employee_name} в {time_str}")
        
        # Отправляем уведомление администратору
        notification_message = f"СКУД: {employee_name}: {event_type} в {time_str} ({date_str})"
        notify_admin(notification_message)
        
        # Возвращаем ответ
        return jsonify({
            'status': 'success',
            'message': 'Данные успешно записаны',
            'employee': employee_name,
            'event': event_type,
            'time': time_str,
            'date': date_str
        })
        
    except Exception as e:
        logger.exception(f"Ошибка при обработке запроса: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Внутренняя ошибка сервера: {str(e)}'
        }), 500

# Маршрут для проверки работоспособности API
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'СКУД API работает нормально',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# Маршрут для главной страницы (панель управления)
@app.route('/dashboard')
def dashboard():
    # Загружаем данные посещаемости
    df = load_attendance_data()
    
    # Текущая дата
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Загружаем список сотрудников
    employees = load_employees()
    
    # Фильтруем записи за сегодня
    today_records = df[df['date'] == today]
    
    # Считаем присутствующих и отсутствующих
    today_present = len(today_records[pd.notna(today_records['arrival']) & pd.isna(today_records['departure'])])
    today_absent = len(employees) - today_present
    
    # Последние события
    recent_events = []
    for _, row in df.sort_values('date', ascending=False).head(5).iterrows():
        event_type = 'приход' if pd.notna(row['arrival']) and pd.isna(row['departure']) else 'уход'
        time_str = row['arrival'] if event_type == 'приход' else row['departure']
        recent_events.append({
            'employee': row['employee'],
            'event_type': event_type,
            'time': time_str,
            'date': row['date']
        })
    
    # Данные для графика посещаемости за неделю
    # Получаем даты за последние 7 дней
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
        if not employee_records.empty and not employee_records['arrival'].isna().all():
            arrival_times = employee_records['arrival'].dropna()
            avg_hour = sum([int(t.split(':')[0]) + int(t.split(':')[1]) / 60 for t in arrival_times]) / len(arrival_times)
            arrival_data.append(round(avg_hour, 2))
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

# Маршрут для страницы посещаемости
@app.route('/attendance')
def attendance():
    # Загружаем данные посещаемости
    df = load_attendance_data()
    
    # Получаем параметры фильтрации
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    selected_employee = request.args.get('employee', '')
    
    # Фильтруем данные
    mask = (df['date'] >= start_date) & (df['date'] <= end_date)
    if selected_employee:
        mask &= (df['employee'] == selected_employee)
    
    filtered_df = df[mask].sort_values(['date', 'employee'], ascending=[False, True])
    
    # Рассчитываем отработанные часы
    attendance_records = []
    for _, row in filtered_df.iterrows():
        hours_worked = None
        if pd.notna(row['arrival']) and pd.notna(row['departure']):
            arrival = datetime.strptime(row['arrival'], '%H:%M')
            departure = datetime.strptime(row['departure'], '%H:%M')
            
            # Если уход раньше прихода, предполагаем, что уход был на следующий день
            if departure < arrival:
                departure = departure + timedelta(days=1)
                
            hours_worked = round((departure - arrival).total_seconds() / 3600, 2)
        
        attendance_records.append({
            'date': row['date'],
            'employee': row['employee'],
            'arrival': row['arrival'],
            'departure': row['departure'],
            'hours_worked': hours_worked
        })
    
    # Получаем список всех сотрудников для фильтра
    employees = load_employees()
    all_employees = list(employees.values())
    
    return render_template('attendance.html',
                          attendance_records=attendance_records,
                          all_employees=all_employees,
                          selected_employee=selected_employee,
                          start_date=start_date,
                          end_date=end_date)

# Маршрут для страницы сотрудников
@app.route('/employees')
def employees():
    # Загружаем список сотрудников
    employees_dict = load_employees()
    
    return render_template('employees.html', employees=employees_dict)

# Маршрут для добавления сотрудника через веб-интерфейс
@app.route('/add_employee', methods=['POST'])
def add_employee_web():
    serial = request.form.get('serial', '').upper()
    name = request.form.get('name', '')
    
    if not serial or not name:
        return jsonify({'status': 'error', 'message': 'Необходимо указать серийный номер и имя'}), 400
    
    # Добавляем сотрудника
    save_new_employee(serial, name)
    
    return redirect(url_for('employees'))

# Маршрут для редактирования сотрудника
@app.route('/edit_employee', methods=['POST'])
def edit_employee():
    serial = request.form.get('serial', '').upper()
    name = request.form.get('name', '')
    
    if not serial or not name:
        return jsonify({'status': 'error', 'message': 'Необходимо указать серийный номер и имя'}), 400
    
    # Обновляем имя сотрудника
    save_new_employee(serial, name)
    
    return redirect(url_for('employees'))

# Маршрут для страницы отчетов
@app.route('/reports')
def reports():
    try:
        # Добавляем отладочную информацию
        logger.info("Запуск функции reports()")
        
        # Загружаем данные посещаемости
        df = load_attendance_data()
        logger.info(f"Загружено записей посещаемости: {len(df)}")
        
        # Получаем список доступных лет
        available_years = []
        if not df.empty:
            available_years = sorted(df['date'].str[:4].unique().tolist())
        if not available_years:
            available_years = [str(datetime.now().year)]
        logger.info(f"Доступные годы: {available_years}")
        
        # Словарь месяцев на русском языке
        months = {
            1: "Январь",
            2: "Февраль",
            3: "Март",
            4: "Апрель",
            5: "Май",
            6: "Июнь",
            7: "Июль",
            8: "Август",
            9: "Сентябрь",
            10: "Октябрь",
            11: "Ноябрь",
            12: "Декабрь"
        }
        
        # Данные для графика среднего времени прихода по дням недели
        weekday_arrival_data = [0] * 7  # Для каждого дня недели
        
        # Преобразуем даты в datetime для определения дня недели
        if not df.empty:
            try:
                df['datetime'] = pd.to_datetime(df['date'])
                df['weekday'] = df['datetime'].dt.weekday
                
                # Группируем по дням недели и считаем среднее время прихода
                for weekday in range(7):
                    weekday_df = df[df['weekday'] == weekday]
                    if not weekday_df.empty and not weekday_df['arrival'].isna().all():
                        arrival_times = weekday_df['arrival'].dropna()
                        logger.info(f"День недели {weekday}, найдено {len(arrival_times)} записей о приходе")
                        avg_hour = sum([int(t.split(':')[0]) + int(t.split(':')[1]) / 60 for t in arrival_times]) / len(arrival_times)
                        weekday_arrival_data[weekday] = round(avg_hour, 2)
            except Exception as e:
                logger.error(f"Ошибка при обработке данных для графика по дням недели: {str(e)}")
                weekday_arrival_data = [0] * 7
        
        # Данные для графика среднего количества рабочих часов по сотрудникам
        employees = load_employees()
        employee_labels = list(employees.values())
        employee_hours_data = []
        
        try:
            for employee in employees.values():
                employee_records = df[df['employee'] == employee]
                total_hours = 0
                count = 0
                
                for _, row in employee_records.iterrows():
                    if pd.notna(row['arrival']) and pd.notna(row['departure']):
                        arrival = datetime.strptime(row['arrival'], '%H:%M')
                        departure = datetime.strptime(row['departure'], '%H:%M')
                        
                        # Если уход раньше прихода, предполагаем, что уход был на следующий день
                        if departure < arrival:
                            departure = departure + timedelta(days=1)
                            
                        hours = (departure - arrival).total_seconds() / 3600
                        total_hours += hours
                        count += 1
                
                avg_hours = round(total_hours / count, 2) if count > 0 else 0
                employee_hours_data.append(avg_hours)
                logger.info(f"Сотрудник {employee}: средние часы работы {avg_hours} (из {count} записей)")
        except Exception as e:
            logger.error(f"Ошибка при обработке данных для графика по сотрудникам: {str(e)}")
            employee_hours_data = [0] * len(employee_labels)
        
        # Получаем список последних отчетов
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        recent_reports = []
        try:
            for filename in os.listdir(reports_dir):
                if filename.endswith('.xlsx') or filename.endswith('.pdf') or filename.endswith('.csv'):
                    file_path = os.path.join(reports_dir, filename)
                    recent_reports.append({
                        'name': filename,
                        'filename': filename
                    })
            
            # Сортируем отчеты по времени создания (новые в начале)
            recent_reports.sort(key=lambda x: os.path.getmtime(os.path.join(reports_dir, x['filename'])), reverse=True)
            recent_reports = recent_reports[:5]  # Только последние 5 отчетов
            logger.info(f"Найдено отчетов: {len(recent_reports)}")
        except Exception as e:
            logger.error(f"Ошибка при получении списка отчетов: {str(e)}")
        
        # Преобразуем данные в JSON для отладки
        logger.info(f"weekday_arrival_data: {weekday_arrival_data}")
        logger.info(f"employee_labels: {employee_labels}")
        logger.info(f"employee_hours_data: {employee_hours_data}")
        
        return render_template('reports.html',
                              available_years=available_years,
                              months=months,
                              recent_reports=recent_reports,
                              weekday_arrival_data=weekday_arrival_data,
                              employee_labels=employee_labels,
                              employee_hours_data=employee_hours_data)
    except Exception as e:
        logger.exception(f"Критическая ошибка в функции reports(): {str(e)}")
        return f"Ошибка при загрузке страницы отчетов: {str(e)}", 500

# Маршрут для генерации отчета
@app.route('/generate_report', methods=['POST'])
def generate_report():
    year = request.form.get('year')
    month = request.form.get('month')
    report_type = request.form.get('report_type', 'excel')
    
    # Здесь должна быть логика генерации отчета
    # Для примера, просто перенаправляем на страницу отчетов
    
    return redirect(url_for('reports'))

# Маршрут для скачивания отчета
@app.route('/download_report/<filename>')
def download_report(filename):
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
    return send_from_directory(reports_dir, filename, as_attachment=True)

# Маршрут для главной страницы (редирект на dashboard)
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    logger.info("Запуск сервера СКУД")
    # Импортируем маршруты после определения всех функций
    # Закомментируем импорт, так как определили маршруты непосредственно в main.py
    # from app import web_routes
    app.run(host='0.0.0.0', port=5000, debug=True) 