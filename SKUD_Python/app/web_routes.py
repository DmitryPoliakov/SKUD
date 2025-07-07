#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import render_template, request, redirect, url_for, send_from_directory, jsonify
from datetime import datetime, timedelta
import pandas as pd
import os
import calendar
import json

# Импортируем функции из main.py
from app.main import app, load_attendance_data, load_employees, save_new_employee

# Маршрут для главной страницы (панель управления)
@app.route('/')
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
    # Загружаем данные посещаемости
    df = load_attendance_data()
    
    # Получаем список доступных лет
    available_years = sorted(df['date'].str[:4].unique().tolist())
    if not available_years:
        available_years = [datetime.now().year]
    
    # Словарь месяцев
    months = {i: calendar.month_name[i] for i in range(1, 13)}
    
    # Данные для графика среднего времени прихода по дням недели
    weekday_arrival_data = [0] * 7  # Для каждого дня недели
    
    # Преобразуем даты в datetime для определения дня недели
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['date'])
        df['weekday'] = df['datetime'].dt.weekday
        
        # Группируем по дням недели и считаем среднее время прихода
        for weekday in range(7):
            weekday_df = df[df['weekday'] == weekday]
            if not weekday_df.empty and not weekday_df['arrival'].isna().all():
                arrival_times = weekday_df['arrival'].dropna()
                avg_hour = sum([int(t.split(':')[0]) + int(t.split(':')[1]) / 60 for t in arrival_times]) / len(arrival_times)
                weekday_arrival_data[weekday] = round(avg_hour, 2)
    
    # Данные для графика среднего количества рабочих часов по сотрудникам
    employees = load_employees()
    employee_labels = list(employees.values())
    employee_hours_data = []
    
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
    
    # Получаем список последних отчетов
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    recent_reports = []
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
    
    return render_template('reports.html',
                          available_years=available_years,
                          months=months,
                          recent_reports=recent_reports,
                          weekday_arrival_data=weekday_arrival_data,
                          employee_labels=employee_labels,
                          employee_hours_data=employee_hours_data)

# Маршрут для генерации отчета
@app.route('/generate_report', methods=['POST'])
def generate_report():
    year = request.form.get('year')
    month = request.form.get('month')
    report_type = request.form.get('report_type', 'excel')
    
    if not year or not month:
        return jsonify({'status': 'error', 'message': 'Необходимо указать год и месяц'}), 400
    
    # Здесь должен быть код для генерации отчета
    # Для примера просто перенаправляем на страницу отчетов
    
    return redirect(url_for('reports'))

# Маршрут для скачивания отчета
@app.route('/download_report/<filename>')
def download_report(filename):
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
    return send_from_directory(reports_dir, filename, as_attachment=True)

# Маршрут для получения статических файлов
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)