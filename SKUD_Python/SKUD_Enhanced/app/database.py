#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модуль для работы с базой данных СКУД Enhanced
"""

import os
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from loguru import logger
from pathlib import Path

from .config import config
from .models import Base


class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize()
    
    def _initialize(self):
        """Инициализация подключения к базе данных"""
        database_url = config.DATABASE_URL
        
        # Настройки для SQLite
        if database_url.startswith('sqlite'):
            connect_args = {
                "check_same_thread": False,
                "timeout": 30
            }
            
            self.engine = create_engine(
                database_url,
                connect_args=connect_args,
                poolclass=StaticPool,
                echo=config.FLASK_DEBUG
            )
            
            # Включаем поддержку внешних ключей для SQLite
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")  # Для лучшей производительности
                cursor.close()
        else:
            # Для других БД (PostgreSQL, MySQL)
            self.engine = create_engine(
                database_url,
                echo=config.FLASK_DEBUG
            )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info(f"База данных инициализирована: {database_url}")
    
    def create_tables(self):
        """Создает все таблицы в базе данных"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Таблицы базы данных созданы")
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}")
            raise
    
    def drop_tables(self):
        """Удаляет все таблицы (используется только для тестов)"""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning("Все таблицы удалены")
        except Exception as e:
            logger.error(f"Ошибка при удалении таблиц: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Контекстный менеджер для работы с сессией"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка в сессии базы данных: {e}")
            raise
        finally:
            session.close()
    
    def get_db_session(self) -> Session:
        """Возвращает новую сессию базы данных (для зависимостей FastAPI/Flask)"""
        return self.SessionLocal()


# Глобальный экземпляр менеджера базы данных
db_manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    """
    Функция-зависимость для получения сессии базы данных
    Используется в Flask маршрутах и Telegram обработчиках
    """
    db = db_manager.get_db_session()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка в сессии базы данных: {e}")
        raise
    finally:
        db.close()


def init_database():
    """Инициализирует базу данных и создает таблицы"""
    try:
        # Убеждаемся, что директория для базы данных существует
        db_path = config.DATABASE_URL.replace('sqlite:///', '')
        if db_path.startswith('./'):
            db_path = os.path.abspath(db_path)
        
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Создана директория для базы данных: {db_dir}")
        
        # Создаем таблицы
        db_manager.create_tables()
        
        # Проверяем подключение
        with db_manager.get_session() as session:
            result = session.execute("SELECT 1").scalar()
            if result == 1:
                logger.success("База данных успешно инициализирована")
            else:
                raise Exception("Ошибка подключения к базе данных")
                
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise


def create_initial_data():
    """Создает начальные данные в базе данных"""
    from .models import Employee, RFIDCard, UserRole
    
    try:
        with db_manager.get_session() as session:
            # Проверяем, есть ли уже администратор
            admin = session.query(Employee).filter(
                Employee.role == UserRole.ADMIN
            ).first()
            
            if not admin and config.TELEGRAM_ADMIN_ID:
                # Создаем администратора
                admin = Employee(
                    name="Администратор",
                    telegram_id=str(config.TELEGRAM_ADMIN_ID),
                    role=UserRole.ADMIN,
                    notifications_enabled=True,
                    arrival_notifications=True,
                    departure_notifications=True
                )
                session.add(admin)
                logger.info("Создан администратор системы")
            
            # Проверяем, есть ли тестовые данные
            existing_cards = session.query(RFIDCard).count()
            
            if existing_cards == 0:
                # Создаем тестовые карты из старой системы для совместимости
                test_cards = [
                    ("992BEE97", "Поляков Павел"),
                    ("894046B8", "Тарасов Никита"),
                    ("E79DF8A4", "Карта МИР 4635"),
                    ("0A711B71", "Карта Прокатут"),
                    ("92C2001D", "Поляков Дмитрий"),
                    ("083BD5D8", "ЦУМ"),
                    ("E9DBA5A3", "Шура"),
                    ("32AABBD6", "Поляков Павел (дубль)"),
                    ("296DD1A3", "Пущинский Марк")
                ]
                
                for serial, name in test_cards:
                    # Создаем сотрудника
                    employee = Employee(
                        name=name,
                        role=UserRole.EMPLOYEE,
                        notifications_enabled=True,
                        arrival_notifications=True,
                        departure_notifications=True
                    )
                    session.add(employee)
                    session.flush()  # Получаем ID
                    
                    # Создаем карту
                    card = RFIDCard(
                        serial_number=serial,
                        employee_id=employee.id,
                        card_type="MIFARE",
                        description=f"Карта для {name}"
                    )
                    session.add(card)
                
                logger.info(f"Созданы тестовые данные: {len(test_cards)} карт")
            
            session.commit()
            logger.success("Начальные данные созданы")
            
    except Exception as e:
        logger.error(f"Ошибка при создании начальных данных: {e}")
        raise


def backup_database(backup_path: str = None):
    """Создает резервную копию базы данных"""
    if not backup_path:
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = config.DATA_DIR / f"backup_skud_{timestamp}.db"
    
    try:
        if config.DATABASE_URL.startswith('sqlite'):
            import shutil
            db_path = config.DATABASE_URL.replace('sqlite:///', '')
            if db_path.startswith('./'):
                db_path = os.path.abspath(db_path)
            
            shutil.copy2(db_path, backup_path)
            logger.info(f"Создана резервная копия базы данных: {backup_path}")
        else:
            logger.warning("Резервное копирование поддерживается только для SQLite")
            
    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        raise


def restore_database(backup_path: str):
    """Восстанавливает базу данных из резервной копии"""
    try:
        if config.DATABASE_URL.startswith('sqlite'):
            import shutil
            db_path = config.DATABASE_URL.replace('sqlite:///', '')
            if db_path.startswith('./'):
                db_path = os.path.abspath(db_path)
            
            # Создаем резервную копию текущей базы
            backup_database(f"{db_path}.before_restore")
            
            # Восстанавливаем из резервной копии
            shutil.copy2(backup_path, db_path)
            
            # Переинициализируем подключения
            db_manager._initialize()
            
            logger.info(f"База данных восстановлена из: {backup_path}")
        else:
            logger.warning("Восстановление поддерживается только для SQLite")
            
    except Exception as e:
        logger.error(f"Ошибка при восстановлении базы данных: {e}")
        raise


def get_database_info():
    """Возвращает информацию о базе данных"""
    try:
        with db_manager.get_session() as session:
            from .models import Employee, RFIDCard, AttendanceEvent, DailyAttendance
            
            info = {
                "database_url": config.DATABASE_URL,
                "employees_count": session.query(Employee).count(),
                "cards_count": session.query(RFIDCard).count(),
                "events_count": session.query(AttendanceEvent).count(),
                "daily_records_count": session.query(DailyAttendance).count(),
            }
            
            # Информация о размере файла (только для SQLite)
            if config.DATABASE_URL.startswith('sqlite'):
                db_path = config.DATABASE_URL.replace('sqlite:///', '')
                if db_path.startswith('./'):
                    db_path = os.path.abspath(db_path)
                
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    size_mb = size_bytes / (1024 * 1024)
                    info["database_size_mb"] = round(size_mb, 2)
                    info["database_path"] = db_path
            
            return info
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о базе данных: {e}")
        return {"error": str(e)} 


def migrate_from_legacy_system(legacy_data_dir: str = "../data"):
    """
    Миграция данных из старой системы (CSV + JSON файлы) в новую SQLite базу
    
    Args:
        legacy_data_dir: Путь к папке с данными старой системы
    """
    from .models import Employee, RFIDCard, AttendanceEvent, EventType, UserRole
    import pandas as pd
    import json
    from datetime import datetime
    
    try:
        logger.info("Начинаю миграцию данных из старой системы...")
        
        legacy_path = Path(legacy_data_dir)
        employees_file = legacy_path / "employees.json"
        attendance_file = legacy_path / "attendance.csv"
        
        if not employees_file.exists():
            logger.warning(f"Файл сотрудников не найден: {employees_file}")
            return False
            
        if not attendance_file.exists():
            logger.warning(f"Файл посещаемости не найден: {attendance_file}")
            return False
        
        with db_manager.get_session() as session:
            # Создаем резервную копию перед миграцией
            backup_database()
            
            # 1. Загружаем сотрудников из employees.json
            logger.info("Миграция сотрудников...")
            with open(employees_file, 'r', encoding='utf-8') as f:
                legacy_employees = json.load(f)
            
            card_to_employee = {}  # Маппинг серийный_номер -> employee_id
            
            for serial_number, employee_name in legacy_employees.items():
                # Проверяем, есть ли уже такая карта
                existing_card = session.query(RFIDCard).filter(
                    RFIDCard.serial_number == serial_number.upper()
                ).first()
                
                if existing_card:
                    logger.info(f"Карта {serial_number} уже существует, пропускаю")
                    card_to_employee[employee_name] = existing_card.employee_id
                    continue
                
                # Проверяем, есть ли сотрудник с таким именем
                existing_employee = session.query(Employee).filter(
                    Employee.name == employee_name
                ).first()
                
                if not existing_employee:
                    # Создаем нового сотрудника
                    employee = Employee(
                        name=employee_name,
                        role=UserRole.EMPLOYEE,
                        notifications_enabled=True,
                        arrival_notifications=True,
                        departure_notifications=True
                    )
                    session.add(employee)
                    session.flush()  # Получаем ID
                    logger.info(f"Создан сотрудник: {employee_name}")
                else:
                    employee = existing_employee
                    logger.info(f"Сотрудник {employee_name} уже существует")
                
                # Создаем карту
                card = RFIDCard(
                    serial_number=serial_number.upper(),
                    employee_id=employee.id,
                    card_type="MIFARE",
                    description=f"Мигрировано из старой системы"
                )
                session.add(card)
                card_to_employee[employee_name] = employee.id
                logger.info(f"Создана карта {serial_number} для {employee_name}")
            
            session.commit()
            
            # 2. Загружаем данные посещаемости из attendance.csv
            logger.info("Миграция данных посещаемости...")
            df = pd.read_csv(attendance_file)
            
            migrated_events = 0
            skipped_events = 0
            
            for _, row in df.iterrows():
                date_str = row['date']
                employee_name = row['employee']
                arrival_time = row['arrival'] if pd.notna(row['arrival']) else None
                departure_time = row['departure'] if pd.notna(row['departure']) else None
                
                if employee_name not in card_to_employee:
                    logger.warning(f"Сотрудник {employee_name} не найден в маппинге, пропускаю")
                    skipped_events += 1
                    continue
                
                employee_id = card_to_employee[employee_name]
                
                # Создаем событие прихода
                if arrival_time:
                    arrival_datetime = datetime.strptime(f"{date_str} {arrival_time}", "%Y-%m-%d %H:%M")
                    
                    # Проверяем, есть ли уже такое событие
                    existing_arrival = session.query(AttendanceEvent).filter(
                        AttendanceEvent.employee_id == employee_id,
                        AttendanceEvent.event_date == date_str,
                        AttendanceEvent.event_type == EventType.ARRIVAL
                    ).first()
                    
                    if not existing_arrival:
                        arrival_event = AttendanceEvent(
                            employee_id=employee_id,
                            event_type=EventType.ARRIVAL,
                            event_time=arrival_datetime,
                            event_date=date_str,
                            local_time=arrival_datetime.time(),
                            notes="Мигрировано из старой системы"
                        )
                        session.add(arrival_event)
                        migrated_events += 1
                
                # Создаем событие ухода
                if departure_time:
                    departure_datetime = datetime.strptime(f"{date_str} {departure_time}", "%Y-%m-%d %H:%M")
                    
                    # Проверяем, есть ли уже такое событие
                    existing_departure = session.query(AttendanceEvent).filter(
                        AttendanceEvent.employee_id == employee_id,
                        AttendanceEvent.event_date == date_str,
                        AttendanceEvent.event_type == EventType.DEPARTURE
                    ).first()
                    
                    if not existing_departure:
                        departure_event = AttendanceEvent(
                            employee_id=employee_id,
                            event_type=EventType.DEPARTURE,
                            event_time=departure_datetime,
                            event_date=date_str,
                            local_time=departure_datetime.time(),
                            notes="Мигрировано из старой системы"
                        )
                        session.add(departure_event)
                        migrated_events += 1
            
            session.commit()
            
            logger.success(f"Миграция завершена!")
            logger.info(f"Создано сотрудников: {len(legacy_employees)}")
            logger.info(f"Создано карт: {len(legacy_employees)}")
            logger.info(f"Мигрировано событий: {migrated_events}")
            logger.info(f"Пропущено событий: {skipped_events}")
            
            return True
            
    except Exception as e:
        logger.error(f"Ошибка при миграции данных: {e}")
        raise


def auto_close_previous_day():
    """
    Автоматическое закрытие незавершенных дней (аналог auto_close.py)
    """
    from .models import Employee, AttendanceEvent, EventType
    from datetime import datetime, timedelta, time
    
    try:
        logger.info("Запуск автоматического закрытия незавершенных дней")
        
        with db_manager.get_session() as session:
            # Получаем вчерашнюю дату
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            default_end_time = time(17, 0)  # 17:00
            
            # Ищем сотрудников, которые пришли вчера, но не ушли
            arrivals = session.query(AttendanceEvent).filter(
                AttendanceEvent.event_date == yesterday,
                AttendanceEvent.event_type == EventType.ARRIVAL
            ).all()
            
            closed_count = 0
            
            for arrival in arrivals:
                # Проверяем, есть ли событие ухода для этого сотрудника
                departure = session.query(AttendanceEvent).filter(
                    AttendanceEvent.employee_id == arrival.employee_id,
                    AttendanceEvent.event_date == yesterday,
                    AttendanceEvent.event_type == EventType.DEPARTURE
                ).first()
                
                if not departure:
                    # Создаем автоматическое событие ухода
                    auto_departure = AttendanceEvent(
                        employee_id=arrival.employee_id,
                        event_type=EventType.DEPARTURE,
                        event_time=datetime.strptime(f"{yesterday} 17:00", "%Y-%m-%d %H:%M"),
                        event_date=yesterday,
                        local_time=default_end_time,
                        notes="Автоматическое закрытие дня"
                    )
                    session.add(auto_departure)
                    closed_count += 1
                    
                    employee_name = arrival.employee.name if arrival.employee else "Неизвестный"
                    logger.info(f"Автоматически закрыт день для {employee_name} на {yesterday}")
            
            session.commit()
            
            if closed_count > 0:
                logger.success(f"Автоматически закрыто дней: {closed_count}")
            else:
                logger.info("Нет незавершенных дней для закрытия")
                
            return closed_count
            
    except Exception as e:
        logger.error(f"Ошибка при автоматическом закрытии дней: {e}")
        raise 