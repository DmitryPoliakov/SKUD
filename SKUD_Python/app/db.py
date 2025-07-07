#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3
import os
import logging
from datetime import datetime

# Настройка логирования
logger = logging.getLogger(__name__)

# Путь к базе данных
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
DB_FILE = os.path.join(DB_DIR, 'skud.db')

# Убедимся, что директория существует
os.makedirs(DB_DIR, exist_ok=True)

def init_db():
    """
    Инициализация базы данных
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Создаем таблицу сотрудников
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Создаем таблицу посещаемости
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            arrival TEXT,
            departure TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
        ''')
        
        conn.commit()
        logger.info("База данных инициализирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def add_employee(serial, name):
    """
    Добавление нового сотрудника
    
    Args:
        serial (str): Серийный номер карты
        name (str): Имя сотрудника
        
    Returns:
        bool: Результат операции
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем, существует ли уже такой серийный номер
        cursor.execute("SELECT id FROM employees WHERE serial = ?", (serial,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем имя существующего сотрудника
            cursor.execute(
                "UPDATE employees SET name = ?, updated_at = ? WHERE serial = ?",
                (name, datetime.now(), serial)
            )
            logger.info(f"Обновлен сотрудник с серийным номером {serial}: {name}")
        else:
            # Добавляем нового сотрудника
            cursor.execute(
                "INSERT INTO employees (serial, name) VALUES (?, ?)",
                (serial, name)
            )
            logger.info(f"Добавлен новый сотрудник: {name} с картой {serial}")
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def get_employee_by_serial(serial):
    """
    Получение информации о сотруднике по серийному номеру
    
    Args:
        serial (str): Серийный номер карты
        
    Returns:
        dict: Информация о сотруднике или None
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # Для получения словаря
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, serial, name FROM employees WHERE serial = ?", (serial,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о сотруднике: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def record_attendance(employee_id, date, arrival=None, departure=None):
    """
    Запись посещаемости
    
    Args:
        employee_id (int): ID сотрудника
        date (str): Дата в формате YYYY-MM-DD
        arrival (str, optional): Время прихода в формате HH:MM
        departure (str, optional): Время ухода в формате HH:MM
        
    Returns:
        bool: Результат операции
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Проверяем, существует ли запись за этот день
        cursor.execute(
            "SELECT id, arrival, departure FROM attendance WHERE employee_id = ? AND date = ?",
            (employee_id, date)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Запись существует, обновляем её
            record_id, existing_arrival, existing_departure = existing
            
            if arrival and not existing_arrival:
                # Записываем приход
                cursor.execute(
                    "UPDATE attendance SET arrival = ?, updated_at = ? WHERE id = ?",
                    (arrival, datetime.now(), record_id)
                )
                event_type = 'приход'
            elif departure and not existing_departure:
                # Записываем уход
                cursor.execute(
                    "UPDATE attendance SET departure = ?, updated_at = ? WHERE id = ?",
                    (departure, datetime.now(), record_id)
                )
                event_type = 'уход'
            elif departure:
                # Обновляем уход
                cursor.execute(
                    "UPDATE attendance SET departure = ?, updated_at = ? WHERE id = ?",
                    (departure, datetime.now(), record_id)
                )
                event_type = 'уход (повтор)'
            else:
                event_type = 'без изменений'
        else:
            # Создаем новую запись
            cursor.execute(
                "INSERT INTO attendance (employee_id, date, arrival, departure) VALUES (?, ?, ?, ?)",
                (employee_id, date, arrival, departure)
            )
            event_type = 'приход' if arrival else 'уход'
        
        conn.commit()
        logger.info(f"Записано событие: {event_type} для сотрудника ID {employee_id} на {date}")
        return True, event_type
    except Exception as e:
        logger.error(f"Ошибка при записи посещаемости: {str(e)}")
        return False, None
    finally:
        if conn:
            conn.close()

def get_monthly_attendance(year, month):
    """
    Получение данных посещаемости за месяц
    
    Args:
        year (int): Год
        month (int): Месяц (1-12)
        
    Returns:
        list: Список записей посещаемости
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Формируем шаблон для поиска по месяцу (YYYY-MM-%)
        date_pattern = f"{year:04d}-{month:02d}-%"
        
        cursor.execute("""
            SELECT a.id, a.date, e.name as employee, a.arrival, a.departure
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.date LIKE ?
            ORDER BY a.date, e.name
        """, (date_pattern,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Ошибка при получении данных посещаемости: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

# Инициализируем базу данных при импорте модуля
init_db() 