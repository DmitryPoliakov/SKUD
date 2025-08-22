#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Сервис для обработки событий посещаемости
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from ..models import (
    Employee, RFIDCard, AttendanceEvent, DailyAttendance,
    EventType, get_card_by_serial, create_attendance_event, get_today_events
)


class AttendanceService:
    """Сервис для обработки посещаемости"""
    
    def __init__(self):
        pass
    
    def process_card_scan(
        self, 
        db: Session, 
        card_serial: str, 
        timestamp: datetime,
        user_agent: str = None,
        ip_address: str = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Обрабатывает сканирование карты
        
        Args:
            db: Сессия базы данных
            card_serial: Серийный номер карты
            timestamp: Время сканирования
            user_agent: User-Agent (для логирования)
            ip_address: IP адрес (для логирования)
            
        Returns:
            Tuple[success, message, event_data]
        """
        try:
            card_serial = card_serial.upper().strip()
            
            # Ищем карту
            card = get_card_by_serial(db, card_serial)
            
            if not card:
                logger.warning(f"Неизвестная карта: {card_serial}")
                return False, f"Неизвестная карта: {card_serial}", {
                    "status": "unknown_card",
                    "card_serial": card_serial,
                    "timestamp": timestamp.isoformat()
                }
            
            if not card.employee:
                logger.warning(f"Карта {card_serial} не привязана к сотруднику")
                return False, f"Карта не привязана к сотруднику", {
                    "status": "unassigned_card",
                    "card_serial": card_serial,
                    "timestamp": timestamp.isoformat()
                }
            
            employee = card.employee
            
            # Определяем тип события (приход или уход)
            event_type = self._determine_event_type(db, employee.id, timestamp)
            
            # Создаем событие посещаемости
            event = create_attendance_event(
                db=db,
                card=card,
                event_type=event_type,
                event_time=timestamp,
                notes=f"IP: {ip_address}, UA: {user_agent}" if ip_address or user_agent else None
            )
            
            # Обновляем дневную посещаемость
            self._update_daily_attendance(db, employee.id, timestamp, event_type)
            
            event_data = {
                "status": "success",
                "employee_id": employee.id,
                "employee_name": employee.name,
                "card_serial": card_serial,
                "event_type": event_type.value,
                "event_time": timestamp.isoformat(),
                "local_time": event.local_time.strftime('%H:%M'),
                "date": event.event_date,
                "telegram_id": employee.telegram_id
            }
            
            action = "приход" if event_type == EventType.ARRIVAL else "уход"
            message = f"Записано: {employee.name} - {action} в {event.local_time.strftime('%H:%M')}"
            
            logger.info(f"Обработано событие: {employee.name} - {action} в {timestamp}")
            
            return True, message, event_data
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сканирования карты: {e}")
            return False, f"Внутренняя ошибка: {str(e)}", None
    
    def _determine_event_type(
        self, 
        db: Session, 
        employee_id: int, 
        timestamp: datetime
    ) -> EventType:
        """
        Определяет тип события (приход или уход) на основе истории
        
        Args:
            db: Сессия базы данных
            employee_id: ID сотрудника
            timestamp: Время события
            
        Returns:
            Тип события
        """
        try:
            # Получаем события за сегодня
            date_str = timestamp.strftime('%Y-%m-%d')
            today_events = get_today_events(db, employee_id, date_str)
            
            if not today_events:
                # Первое событие за день = приход
                return EventType.ARRIVAL
            
            # Сортируем события по времени
            today_events.sort(key=lambda x: x.event_time)
            last_event = today_events[-1]
            
            # Проверяем интервал между событиями
            time_diff = timestamp - last_event.event_time
            
            # Если прошло меньше 5 минут - считаем ошибочным сканированием
            if time_diff < timedelta(minutes=5):
                logger.warning(f"Повторное сканирование через {time_diff}: игнорируем")
                return last_event.event_type  # Возвращаем тот же тип
            
            # Если последнее событие - приход, то текущее - уход (и наоборот)
            if last_event.event_type == EventType.ARRIVAL:
                return EventType.DEPARTURE
            else:
                return EventType.ARRIVAL
                
        except Exception as e:
            logger.error(f"Ошибка определения типа события: {e}")
            # По умолчанию возвращаем приход
            return EventType.ARRIVAL
    
    def _update_daily_attendance(
        self, 
        db: Session, 
        employee_id: int, 
        timestamp: datetime, 
        event_type: EventType
    ):
        """
        Обновляет дневную статистику посещаемости
        
        Args:
            db: Сессия базы данных
            employee_id: ID сотрудника
            timestamp: Время события
            event_type: Тип события
        """
        try:
            date_str = timestamp.strftime('%Y-%m-%d')
            
            # Ищем существующую запись
            daily_record = db.query(DailyAttendance).filter(
                DailyAttendance.employee_id == employee_id,
                DailyAttendance.date == date_str
            ).first()
            
            if not daily_record:
                # Создаем новую запись
                daily_record = DailyAttendance(
                    employee_id=employee_id,
                    date=date_str,
                    is_weekend=self._is_weekend(timestamp),
                    is_holiday=self._is_holiday(timestamp)
                )
                db.add(daily_record)
            
            # Обновляем времена
            if event_type == EventType.ARRIVAL:
                if not daily_record.arrival_time or timestamp < daily_record.arrival_time:
                    daily_record.arrival_time = timestamp
            elif event_type == EventType.DEPARTURE:
                daily_record.departure_time = timestamp
            
            # Вычисляем отработанные часы
            if daily_record.arrival_time and daily_record.departure_time:
                duration = daily_record.departure_time - daily_record.arrival_time
                
                # Если уход раньше прихода, предполагаем уход на следующий день
                if duration.total_seconds() < 0:
                    duration = (daily_record.departure_time + timedelta(days=1)) - daily_record.arrival_time
                
                daily_record.hours_worked = int(duration.total_seconds() // 60)  # В минутах
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Ошибка обновления дневной посещаемости: {e}")
    
    def _is_weekend(self, timestamp: datetime) -> bool:
        """Проверяет, является ли день выходным"""
        return timestamp.weekday() >= 5  # Суббота=5, Воскресенье=6
    
    def _is_holiday(self, timestamp: datetime) -> bool:
        """Проверяет, является ли день праздничным"""
        # TODO: Можно добавить проверку праздничных дней
        # Пока возвращаем False
        return False
    
    def get_employee_daily_summary(
        self, 
        db: Session, 
        employee_id: int, 
        date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получает дневную сводку по сотруднику
        
        Args:
            db: Сессия базы данных
            employee_id: ID сотрудника
            date: Дата в формате YYYY-MM-DD (по умолчанию сегодня)
            
        Returns:
            Словарь с информацией о дне
        """
        try:
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Получаем события за день
            events = get_today_events(db, employee_id, date)
            
            # Получаем дневную запись
            daily_record = db.query(DailyAttendance).filter(
                DailyAttendance.employee_id == employee_id,
                DailyAttendance.date == date
            ).first()
            
            # Получаем информацию о сотруднике
            employee = db.query(Employee).filter(Employee.id == employee_id).first()
            
            summary = {
                "employee_id": employee_id,
                "employee_name": employee.name if employee else "Неизвестно",
                "date": date,
                "events_count": len(events),
                "arrival_time": None,
                "departure_time": None,
                "hours_worked": None,
                "is_weekend": self._is_weekend(datetime.strptime(date, '%Y-%m-%d')),
                "is_present": False,
                "events": []
            }
            
            # Заполняем события
            for event in events:
                summary["events"].append({
                    "type": event.event_type.value,
                    "time": event.local_time.strftime('%H:%M'),
                    "timestamp": event.event_time.isoformat()
                })
            
            # Заполняем данные из дневной записи
            if daily_record:
                if daily_record.arrival_time:
                    summary["arrival_time"] = daily_record.arrival_time.strftime('%H:%M')
                if daily_record.departure_time:
                    summary["departure_time"] = daily_record.departure_time.strftime('%H:%M')
                if daily_record.hours_worked:
                    hours = daily_record.hours_worked // 60
                    minutes = daily_record.hours_worked % 60
                    summary["hours_worked"] = f"{hours:02d}:{minutes:02d}"
                
                # Определяем, присутствует ли сотрудник
                summary["is_present"] = (
                    daily_record.arrival_time is not None and 
                    daily_record.departure_time is None
                )
            
            return summary
            
        except Exception as e:
            logger.error(f"Ошибка получения дневной сводки: {e}")
            return None
    
    def get_monthly_statistics(
        self, 
        db: Session, 
        employee_id: int = None, 
        year: int = None, 
        month: int = None
    ) -> Dict[str, Any]:
        """
        Получает месячную статистику
        
        Args:
            db: Сессия базы данных
            employee_id: ID сотрудника (если None - по всем)
            year: Год (по умолчанию текущий)
            month: Месяц (по умолчанию текущий)
            
        Returns:
            Словарь со статистикой
        """
        try:
            if not year or not month:
                now = datetime.now()
                year = year or now.year
                month = month or now.month
            
            # Формируем период
            start_date = f"{year:04d}-{month:02d}-01"
            
            # Последний день месяца
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
            
            # Базовый запрос
            query = db.query(DailyAttendance).filter(
                DailyAttendance.date >= start_date,
                DailyAttendance.date <= end_date
            )
            
            if employee_id:
                query = query.filter(DailyAttendance.employee_id == employee_id)
            
            records = query.all()
            
            # Статистика
            total_records = len(records)
            total_hours = sum(r.hours_worked or 0 for r in records)
            total_days = len(set(r.date for r in records))
            
            # Группировка по сотрудникам
            employee_stats = {}
            for record in records:
                emp_id = record.employee_id
                if emp_id not in employee_stats:
                    employee_stats[emp_id] = {
                        "employee_id": emp_id,
                        "total_days": 0,
                        "total_hours": 0,
                        "weekend_days": 0
                    }
                
                employee_stats[emp_id]["total_days"] += 1
                employee_stats[emp_id]["total_hours"] += record.hours_worked or 0
                if record.is_weekend:
                    employee_stats[emp_id]["weekend_days"] += 1
            
            return {
                "period": f"{month:02d}.{year}",
                "total_records": total_records,
                "total_hours_minutes": total_hours,
                "total_hours_formatted": f"{total_hours // 60:02d}:{total_hours % 60:02d}",
                "total_unique_days": total_days,
                "unique_employees": len(employee_stats),
                "employee_statistics": list(employee_stats.values())
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения месячной статистики: {e}")
            return {}
    
    def auto_close_day(
        self, 
        db: Session, 
        date: str = None, 
        default_departure_time: str = "17:00"
    ) -> int:
        """
        Автоматически закрывает день для незакрытых записей
        
        Args:
            db: Сессия базы данных
            date: Дата для закрытия (по умолчанию вчера)
            default_departure_time: Время ухода по умолчанию
            
        Returns:
            Количество закрытых записей
        """
        try:
            if not date:
                yesterday = datetime.now() - timedelta(days=1)
                date = yesterday.strftime('%Y-%m-%d')
            
            # Ищем незакрытые записи
            unclosed_records = db.query(DailyAttendance).filter(
                DailyAttendance.date == date,
                DailyAttendance.arrival_time.isnot(None),
                DailyAttendance.departure_time.is_(None),
                DailyAttendance.is_closed == False
            ).all()
            
            closed_count = 0
            
            for record in unclosed_records:
                try:
                    # Устанавливаем время ухода
                    departure_datetime = datetime.strptime(
                        f"{date} {default_departure_time}", 
                        '%Y-%m-%d %H:%M'
                    )
                    
                    record.departure_time = departure_datetime
                    record.is_closed = True
                    record.auto_closed = True
                    
                    # Пересчитываем отработанные часы
                    if record.arrival_time:
                        duration = departure_datetime - record.arrival_time
                        record.hours_worked = int(duration.total_seconds() // 60)
                    
                    closed_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка закрытия записи {record.id}: {e}")
                    continue
            
            if closed_count > 0:
                db.commit()
                logger.info(f"Автоматически закрыто {closed_count} записей за {date}")
            
            return closed_count
            
        except Exception as e:
            logger.error(f"Ошибка автозакрытия дня: {e}")
            return 0 