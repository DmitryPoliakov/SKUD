#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Основное Flask приложение для системы СКУД Enhanced
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory
from flask_cors import CORS
from loguru import logger

from .config import config
from .database import get_db, init_database, create_initial_data, get_database_info
from .models import Employee, RFIDCard, AttendanceEvent, RegistrationRequest, EventType
from .services import AttendanceService, RegistrationService, NotificationService, ReportService
from .telegram_bot import bot, send_attendance_notification, send_admin_notification, send_unknown_card_notification
from .models import UserRole


# Создаем Flask приложение
app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

# Настройка Flask
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    DEBUG=config.FLASK_DEBUG
)

# Включаем CORS для API
CORS(app, resources={"/api/*": {"origins": "*"}})

# Инициализируем сервисы
attendance_service = AttendanceService()
registration_service = RegistrationService()
notification_service = NotificationService()
report_service = ReportService()


@app.before_first_request
def initialize_app():
    """Инициализация приложения при первом запуске"""
    try:
        logger.info("Инициализация СКУД Enhanced...")
        
        # Инициализируем базу данных
        init_database()
        
        # Создаем начальные данные
        create_initial_data()
        
        logger.success("СКУД Enhanced успешно инициализирован")
        
    except Exception as e:
        logger.error(f"Ошибка инициализации приложения: {e}")
        raise


# ================================
# API ENDPOINTS
# ================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности системы"""
    try:
        db_info = get_database_info()
        
        return jsonify({
            'status': 'ok',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'Система СКУД Enhanced работает нормально',
            'version': '2.0.0',
            'database': db_info
        })
    except Exception as e:
        logger.error(f"Ошибка health check: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500


@app.route('/api/attendance', methods=['POST'])
def record_attendance():
    """API endpoint для обработки запросов от ESP32 (полная совместимость со старой системой)"""
    try:
        data = request.json
        logger.info(f"Получены данные: {data}")
        
        if not data or 'serial' not in data or 'time' not in data:
            logger.error("Неверный формат данных")
            return jsonify({
                'status': 'error',
                'message': 'Неверный формат данных'
            }), 400
        
        card_serial = data['serial']
        timestamp_str = data['time']
        
        # Получаем дополнительную информацию для логирования
        user_agent = request.headers.get('User-Agent')
        ip_address = request.remote_addr
        
        # Парсим timestamp
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.error(f"Неверный формат времени: {timestamp_str}")
            return jsonify({
                'status': 'error',
                'message': 'Неверный формат времени'
            }), 400
        
        # Обрабатываем событие через сервис
        with next(get_db()) as db:
            success, message, event_data = attendance_service.process_card_scan(
                db=db,
                card_serial=card_serial,
                timestamp=timestamp,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            if success:
                # Отправляем уведомления
                if event_data.get('telegram_id'):
                    # Уведомление сотруднику
                    asyncio.create_task(send_attendance_notification(
                        telegram_id=event_data['telegram_id'],
                        employee_name=event_data['employee_name'],
                        event_type=event_data['event_type'],
                        event_time=event_data['local_time'],
                        date=event_data['date']
                    ))
                
                # Уведомление администратору
                admin_message = (
                    f"СКУД: {event_data['employee_name']}: "
                    f"{event_data['event_type']} в {event_data['local_time']} ({event_data['date']})"
                )
                asyncio.create_task(send_admin_notification(admin_message))
                
                # Возвращаем ответ в формате, совместимом со старым ESP32 кодом
                return jsonify({
                    'status': 'success',
                    'message': 'Данные успешно записаны',
                    'employee': event_data['employee_name'],  # Для совместимости со старым кодом
                    'event': 'приход' if event_data['event_type'] == 'arrival' else 'уход',  # Переводим на русский
                    'time': event_data['local_time'],
                    'date': event_data['date']
                })
            else:
                # Обработка ошибок
                if event_data and event_data.get('status') == 'unknown_card':
                    # Уведомление администратору о неизвестной карте
                    admin_message = (
                        f"СКУД: Обнаружена неизвестная карта: {card_serial}\n\n"
                        f"Для добавления сотрудника отправьте команду:\n"
                        f"/add_employee {card_serial} Имя_Сотрудника"
                    )
                    asyncio.create_task(send_unknown_card_notification(card_serial, admin_message))
                    
                    return jsonify({
                        'status': 'unknown',  # Для совместимости со старым ESP32 кодом
                        'message': f'Неизвестный ключ: {card_serial}'
                    }), 404
                else:
                    return jsonify({
                        'status': 'error',
                        'message': message
                    }), 400
                    
    except Exception as e:
        logger.error(f"Ошибка при обработке события посещаемости: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Внутренняя ошибка сервера: {str(e)}'
        }), 500


@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Получение списка сотрудников"""
    try:
        with next(get_db()) as db:
            employees = db.query(Employee).filter(Employee.is_active == True).all()
            
            result = []
            for emp in employees:
                result.append({
                    'id': emp.id,
                    'name': emp.name,
                    'telegram_id': emp.telegram_id,
                    'role': emp.role.value,
                    'cards_count': len(emp.get_active_cards()),
                    'notifications_enabled': emp.notifications_enabled,
                    'created_at': emp.created_at.isoformat() if emp.created_at else None
                })
            
            return jsonify({
                'status': 'success',
                'data': result,
                'total': len(result)
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения списка сотрудников: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/current-stats', methods=['GET'])
def current_stats():
    """Получение текущей статистики"""
    try:
        with next(get_db()) as db:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Общее количество сотрудников
            total_employees = db.query(Employee).filter(Employee.is_active == True).count()
            
            # Сегодняшние события
            today_events = db.query(AttendanceEvent).filter(
                AttendanceEvent.event_date == today
            ).all()
            
            # Присутствующие сегодня (есть приход, нет ухода)
            present_employees = set()
            for event in today_events:
                if event.event_type == EventType.ARRIVAL:
                    present_employees.add(event.employee_id)
                elif event.event_type == EventType.DEPARTURE:
                    present_employees.discard(event.employee_id)
            
            return jsonify({
                'status': 'success',
                'data': {
                    'total_employees': total_employees,
                    'present_today': len(present_employees),
                    'events_today': len(today_events),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            })
            
    except Exception as e:
        logger.error(f"Ошибка получения текущей статистики: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ================================
# WEB ROUTES
# ================================

@app.route('/')
def index():
    """Главная страница - редирект на дашборд"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Панель управления"""
    try:
        with next(get_db()) as db:
            # Получаем статистику для дашборда
            stats = get_dashboard_stats(db)
            
            return render_template('dashboard.html', **stats)
            
    except Exception as e:
        logger.error(f"Ошибка загрузки дашборда: {e}")
        return f"Ошибка загрузки дашборда: {e}", 500


@app.route('/attendance')
def attendance():
    """Страница посещаемости с фильтрацией"""
    try:
        import pandas as pd
        
        with next(get_db()) as db:
            # Получаем параметры фильтрации
            start_date = request.args.get('start_date', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
            end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
            selected_employee = request.args.get('employee', '')
            
            # Запрос событий посещаемости
            query = db.query(AttendanceEvent).filter(
                AttendanceEvent.event_date >= start_date,
                AttendanceEvent.event_date <= end_date
            )
            
            if selected_employee:
                query = query.join(Employee).filter(Employee.name == selected_employee)
            
            events = query.order_by(
                AttendanceEvent.event_date.desc(),
                AttendanceEvent.local_time.desc()
            ).all()
            
            # Группируем события по дате и сотруднику
            attendance_records = {}
            for event in events:
                key = (event.event_date, event.employee.name)
                if key not in attendance_records:
                    attendance_records[key] = {
                        'date': event.event_date,
                        'employee': event.employee.name,
                        'arrival': None,
                        'departure': None,
                        'hours_worked': None
                    }
                
                if event.event_type == EventType.ARRIVAL:
                    attendance_records[key]['arrival'] = event.local_time.strftime('%H:%M')
                elif event.event_type == EventType.DEPARTURE:
                    attendance_records[key]['departure'] = event.local_time.strftime('%H:%M')
            
            # Рассчитываем отработанные часы
            for record in attendance_records.values():
                if record['arrival'] and record['departure']:
                    arrival = datetime.strptime(record['arrival'], '%H:%M')
                    departure = datetime.strptime(record['departure'], '%H:%M')
                    
                    # Если уход раньше прихода, предполагаем, что уход был на следующий день
                    if departure < arrival:
                        departure = departure + timedelta(days=1)
                    
                    hours_worked = (departure - arrival).total_seconds() / 3600
                    record['hours_worked'] = round(hours_worked, 2)
            
            # Получаем список всех сотрудников для фильтра
            all_employees = db.query(Employee).filter(Employee.is_active == True).all()
            employee_names = [emp.name for emp in all_employees]
            
            attendance_list = list(attendance_records.values())
            attendance_list.sort(key=lambda x: (x['date'], x['employee']), reverse=True)
            
            return render_template('attendance.html',
                                  attendance_records=attendance_list,
                                  all_employees=employee_names,
                                  selected_employee=selected_employee,
                                  start_date=start_date,
                                  end_date=end_date)
                                  
    except Exception as e:
        logger.error(f"Ошибка страницы посещаемости: {e}")
        return f"Ошибка при загрузке страницы посещаемости: {str(e)}", 500


@app.route('/employees')
def employees():
    """Страница управления сотрудниками"""
    try:
        with next(get_db()) as db:
            employees_list = db.query(Employee).filter(Employee.is_active == True).all()
            
            # Создаем словарь карт для совместимости с шаблоном
            employees_dict = {}
            for emp in employees_list:
                active_cards = emp.get_active_cards()
                if active_cards:
                    # Берем первую активную карту для отображения
                    employees_dict[active_cards[0].serial_number] = emp.name
            
            return render_template('employees.html', employees=employees_dict)
            
    except Exception as e:
        logger.error(f"Ошибка страницы сотрудников: {e}")
        return f"Ошибка при загрузке страницы сотрудников: {str(e)}", 500


@app.route('/add_employee', methods=['POST'])
def add_employee_web():
    """Добавление сотрудника через веб-интерфейс"""
    try:
        serial = request.form.get('serial', '').upper().strip()
        name = request.form.get('name', '').strip()
        
        if not serial or not name:
            return jsonify({'status': 'error', 'message': 'Необходимо указать серийный номер и имя'}), 400
        
        with next(get_db()) as db:
            # Проверяем, есть ли уже такая карта
            existing_card = db.query(RFIDCard).filter(
                RFIDCard.serial_number == serial
            ).first()
            
            if existing_card:
                return jsonify({'status': 'error', 'message': 'Карта с таким серийным номером уже существует'}), 400
            
            # Создаем сотрудника
            employee = Employee(
                name=name,
                role=UserRole.EMPLOYEE,
                notifications_enabled=True,
                arrival_notifications=True,
                departure_notifications=True
            )
            db.add(employee)
            db.flush()  # Получаем ID
            
            # Создаем карту
            card = RFIDCard(
                serial_number=serial,
                employee_id=employee.id,
                card_type="MIFARE",
                description=f"Добавлено через веб-интерфейс"
            )
            db.add(card)
            db.commit()
            
            logger.info(f"Добавлен сотрудник {name} с картой {serial}")
        
        return redirect(url_for('employees'))
        
    except Exception as e:
        logger.error(f"Ошибка добавления сотрудника: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/edit_employee', methods=['POST'])
def edit_employee():
    """Редактирование сотрудника"""
    try:
        serial = request.form.get('serial', '').upper().strip()
        name = request.form.get('name', '').strip()
        
        if not serial or not name:
            return jsonify({'status': 'error', 'message': 'Необходимо указать серийный номер и имя'}), 400
        
        with next(get_db()) as db:
            # Ищем карту
            card = db.query(RFIDCard).filter(
                RFIDCard.serial_number == serial
            ).first()
            
            if not card:
                return jsonify({'status': 'error', 'message': 'Карта не найдена'}), 404
            
            # Обновляем имя сотрудника
            if card.employee:
                card.employee.name = name
                card.employee.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            logger.info(f"Обновлено имя сотрудника для карты {serial}: {name}")
        
        return redirect(url_for('employees'))
        
    except Exception as e:
        logger.error(f"Ошибка редактирования сотрудника: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reports')
def reports():
    """Страница отчетов"""
    try:
        with next(get_db()) as db:
            # Получаем доступные годы из событий
            years_query = db.query(AttendanceEvent.event_date).distinct().all()
            available_years = []
            if years_query:
                dates = [date[0] for date in years_query if date[0]]
                years = set([d[:4] for d in dates])
                available_years = sorted(list(years))
            
            if not available_years:
                available_years = [str(datetime.now().year)]
            
            # Словарь месяцев на русском языке
            import calendar
            months = {
                1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
                5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
                9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
            }
            
            # Получаем список отчетов
            reports_dir = config.DATA_DIR / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            recent_reports = []
            try:
                for file_path in reports_dir.glob("*"):
                    if file_path.suffix in ['.xlsx', '.pdf', '.csv']:
                        recent_reports.append({
                            'name': file_path.name,
                            'filename': file_path.name
                        })
                
                # Сортируем по времени создания
                recent_reports.sort(key=lambda x: (reports_dir / x['filename']).stat().st_mtime, reverse=True)
                recent_reports = recent_reports[:5]
                
            except Exception as e:
                logger.warning(f"Ошибка при получении списка отчетов: {e}")
            
            # Данные для графиков (упрощенная версия для начала)
            weekday_arrival_data = [8.5, 8.7, 8.3, 8.4, 8.2, 0, 0]  # Пн-Вс
            employee_labels = []
            employee_hours_data = []
            
            # Получаем сотрудников для графика
            employees = db.query(Employee).filter(Employee.is_active == True).limit(10).all()
            for emp in employees:
                employee_labels.append(emp.name)
                employee_hours_data.append(8.0)  # Среднее значение, можно улучшить
            
            return render_template('reports.html',
                                  available_years=available_years,
                                  months=months,
                                  recent_reports=recent_reports,
                                  weekday_arrival_data=weekday_arrival_data,
                                  employee_labels=employee_labels,
                                  employee_hours_data=employee_hours_data)
                                  
    except Exception as e:
        logger.error(f"Ошибка страницы отчетов: {e}")
        return f"Ошибка при загрузке страницы отчетов: {str(e)}", 500


@app.route('/generate_report', methods=['POST'])
def generate_report():
    """Генерация отчета"""
    try:
        year = request.form.get('year')
        month = request.form.get('month')
        report_type = request.form.get('report_type', 'excel')
        
        if not year or not month:
            return jsonify({'status': 'error', 'message': 'Необходимо указать год и месяц'}), 400
        
        # Импортируем сервис отчетов
        from .services.reports import ReportsService
        
        reports_service = ReportsService()
        
        with next(get_db()) as db:
            # Временно используем простую заглушку для генерации отчета
            logger.info(f"Запрос на генерацию отчета за {month}/{year}")
            
            # Создаем директорию отчетов если не существует
            reports_dir = config.DATA_DIR / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Имя файла отчета
            import calendar
            month_name = calendar.month_name[int(month)]
            filename = f"attendance_report_{year}_{month:0>2}_{month_name}.xlsx"
            
            # Здесь должна быть логика генерации отчета
            # Пока просто создаем заглушку
            report_path = reports_dir / filename
            
            # Простейший Excel файл для тестирования
            try:
                import pandas as pd
                df = pd.DataFrame({
                    'Дата': ['2024-01-01'],
                    'Сотрудник': ['Тест'],
                    'Приход': ['09:00'],
                    'Уход': ['18:00']
                })
                df.to_excel(report_path, index=False)
                
                logger.info(f"Сгенерирован отчет: {report_path}")
                return jsonify({
                    'status': 'success',
                    'message': f'Отчет за {month}/{year} сгенерирован',
                    'file': filename
                })
            except Exception as e:
                logger.error(f"Ошибка создания Excel файла: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Не удалось создать Excel файл'
                }), 500
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/download_report/<filename>')
def download_report(filename):
    """Скачивание отчета"""
    try:
        reports_dir = config.DATA_DIR / "reports"
        return send_from_directory(str(reports_dir), filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Ошибка скачивания отчета: {e}")
        return "Файл не найден", 404


@app.route('/telegram-reports')
def telegram_reports():
    """Страница отчетов для Telegram Web App"""
    try:
        with next(get_db()) as db:
            # Текущая статистика
            today = datetime.now().strftime('%Y-%m-%d')
            
            total_employees = db.query(Employee).filter(Employee.is_active == True).count()
            
            # Присутствующие сегодня
            today_events = db.query(AttendanceEvent).filter(
                AttendanceEvent.event_date == today
            ).all()
            
            present_employees = set()
            for event in today_events:
                if event.event_type == EventType.ARRIVAL:
                    present_employees.add(event.employee_id)
                elif event.event_type == EventType.DEPARTURE:
                    present_employees.discard(event.employee_id)
            
            # Доступные годы и месяцы
            years_query = db.query(AttendanceEvent.event_date).distinct().all()
            available_years = []
            if years_query:
                dates = [date[0] for date in years_query if date[0]]
                years = set([d[:4] for d in dates])
                available_years = sorted(list(years))
            
            if not available_years:
                available_years = [str(datetime.now().year)]
            
            import calendar
            months = {
                1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
                5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
                9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
            }
            
            # Получаем список отчетов
            reports_dir = config.DATA_DIR / "reports"
            reports_dir.mkdir(exist_ok=True)
            
            recent_reports = []
            try:
                for file_path in reports_dir.glob("*"):
                    if file_path.suffix in ['.xlsx', '.pdf', '.csv']:
                        recent_reports.append({
                            'name': file_path.name,
                            'filename': file_path.name
                        })
                
                recent_reports.sort(key=lambda x: (reports_dir / x['filename']).stat().st_mtime, reverse=True)
                recent_reports = recent_reports[:5]
                
            except Exception as e:
                logger.warning(f"Ошибка при получении списка отчетов: {e}")
            
            return render_template('telegram-reports.html',
                                  available_years=available_years,
                                  months=months,
                                  recent_reports=recent_reports,
                                  today_present=len(present_employees),
                                  total_employees=total_employees)
                                  
    except Exception as e:
        logger.error(f"Ошибка Telegram отчетов: {e}")
        return f"Ошибка при загрузке страницы отчетов: {str(e)}", 500


# ================================
# HELPER FUNCTIONS
# ================================

def get_dashboard_stats(db) -> dict:
    """Получает статистику для дашборда"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Общая статистика
        total_employees = db.query(Employee).filter(Employee.is_active == True).count()
        total_cards = db.query(RFIDCard).filter(RFIDCard.is_active == True).count()
        
        # События за сегодня
        today_events = db.query(AttendanceEvent).filter(
            AttendanceEvent.event_date == today
        ).all()
        
        # Присутствующие
        present_employees = set()
        for event in today_events:
            if event.event_type == EventType.ARRIVAL:
                present_employees.add(event.employee_id)
            elif event.event_type == EventType.DEPARTURE:
                present_employees.discard(event.employee_id)
        
        # Последние события
        recent_events = db.query(AttendanceEvent).join(Employee).order_by(
            AttendanceEvent.event_time.desc()
        ).limit(10).all()
        
        return {
            'total_employees': total_employees,
            'total_cards': total_cards,
            'present_today': len(present_employees),
            'events_today': len(today_events),
            'recent_events': recent_events
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики дашборда: {e}")
        return {}


def get_attendance_data(db, start_date=None, end_date=None, employee_id=None) -> list:
    """Получает данные посещаемости с фильтрацией"""
    try:
        # Базовый запрос
        query = db.query(AttendanceEvent).join(Employee)
        
        # Применяем фильтры
        if start_date:
            query = query.filter(AttendanceEvent.event_date >= start_date)
        
        if end_date:
            query = query.filter(AttendanceEvent.event_date <= end_date)
        
        if employee_id:
            query = query.filter(AttendanceEvent.employee_id == employee_id)
        
        # Сортировка
        events = query.order_by(
            AttendanceEvent.event_date.desc(),
            AttendanceEvent.event_time.desc()
        ).limit(500).all()  # Ограничиваем количество записей
        
        return events
        
    except Exception as e:
        logger.error(f"Ошибка получения данных посещаемости: {e}")
        return []


# ================================
# ASYNC NOTIFICATION FUNCTIONS
# ================================

async def send_notifications(event_data):
    """Отправляет уведомления о событии посещаемости"""
    try:
        # Уведомление администратору
        admin_message = (
            f"СКУД: {event_data['employee_name']}: "
            f"{event_data['event_type']} в {event_data['local_time']} "
            f"({event_data['date']})"
        )
        
        if config.TELEGRAM_ADMIN_ID:
            await send_admin_notification(admin_message)
        
        # Уведомление сотруднику (если есть Telegram ID)
        if event_data.get('telegram_id'):
            # Здесь нужно получить объекты Employee и AttendanceEvent
            # для отправки уведомления через сервис
            pass  # TODO: Реализовать отправку уведомления сотруднику
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомлений: {e}")


async def send_unknown_card_alert(card_serial, timestamp):
    """Отправляет уведомление о неизвестной карте"""
    try:
        if config.TELEGRAM_ADMIN_ID:
            await send_unknown_card_notification(card_serial, timestamp)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о неизвестной карте: {e}")


# ================================
# ERROR HANDLERS
# ================================

@app.errorhandler(404)
def not_found(error):
    """Обработчик ошибки 404"""
    if request.path.startswith('/api/'):
        return jsonify({
            'status': 'error',
            'message': 'Endpoint не найден'
        }), 404
    else:
        return render_template('error.html', 
                             error_code=404, 
                             error_message="Страница не найдена"), 404


@app.errorhandler(500)
def internal_error(error):
    """Обработчик ошибки 500"""
    logger.error(f"Внутренняя ошибка сервера: {error}")
    
    if request.path.startswith('/api/'):
        return jsonify({
            'status': 'error',
            'message': 'Внутренняя ошибка сервера'
        }), 500
    else:
        return render_template('error.html', 
                             error_code=500, 
                             error_message="Внутренняя ошибка сервера"), 500


# ================================
# APPLICATION FACTORY
# ================================

def create_app():
    """Фабрика приложений"""
    return app


if __name__ == '__main__':
    # Запуск в режиме разработки
    logger.info(f"Запуск СКУД Enhanced на {config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG
    ) 