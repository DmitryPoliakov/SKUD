#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
from datetime import datetime

# Данные сотрудников
EMPLOYEES = {
    "E9DBA5A3": "Шура",
    "992BEE97": "Поляков Павел", 
    "894046B8": "Тарасов Никита",
    "92C2001D": "Поляков Дмитрий",
    "296DD1A3": "Пущинский Марк",
    "32AABBD6": "Поляков Павел (карта 2)",
    "E79DF8A4": "Карта МИР 4635",
    "0A711B71": "Карта Прокатут", 
    "083BD5D8": "ЦУМ"
}

SERVER_URL = "https://skud-ek.ru/api/attendance"

def send_attendance(serial, time_str=None):
    """
    Отправляет данные посещаемости на сервер
    
    Args:
        serial (str): Серийный номер карты
        time_str (str): Время в формате YYYY-MM-DD HH:MM:SS (опционально)
    """
    
    if time_str is None:
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    employee_name = EMPLOYEES.get(serial, "Неизвестный")
    
    data = {
        "serial": serial,
        "time": time_str
    }
    
    print(f"📤 Отправка данных:")
    print(f"   Сотрудник: {employee_name}")
    print(f"   Серийный номер: {serial}")
    print(f"   Время: {time_str}")
    print(f"   URL: {SERVER_URL}")
    print()
    
    try:
        response = requests.post(
            SERVER_URL, 
            json=data, 
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"✅ Успешно!")
                print(f"   Сотрудник: {result.get('employee')}")
                print(f"   Событие: {result.get('event')}")
                print(f"   Время: {result.get('time')}")
                print(f"   Дата: {result.get('date')}")
            else:
                print(f"❌ Ошибка сервера: {result.get('message')}")
        else:
            print(f"❌ HTTP ошибка {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка соединения: {e}")

def main():
    print("🔑 СКУД - Отправка данных посещаемости")
    print("=" * 50)
    
    # Показываем список сотрудников
    print("\n👥 Доступные сотрудники:")
    for i, (serial, name) in enumerate(EMPLOYEES.items(), 1):
        print(f"   {i}. {name} ({serial})")
    
    print(f"\n   {len(EMPLOYEES) + 1}. Ввести серийный номер вручную")
    print()
    
    try:
        choice = input("Выберите сотрудника (номер): ").strip()
        
        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(EMPLOYEES):
                serial = list(EMPLOYEES.keys())[choice_num - 1]
            elif choice_num == len(EMPLOYEES) + 1:
                serial = input("Введите серийный номер карты: ").strip().upper()
                if not serial:
                    print("❌ Серийный номер не может быть пустым")
                    return
            else:
                print("❌ Неверный выбор")
                return
        else:
            print("❌ Введите номер")
            return
        
        # Спрашиваем время
        time_choice = input("\nИспользовать текущее время? (y/n): ").strip().lower()
        
        if time_choice in ['y', 'yes', 'да', '']:
            time_str = None
        else:
            time_str = input("Введите время (YYYY-MM-DD HH:MM:SS): ").strip()
            if not time_str:
                time_str = None
        
        print()
        send_attendance(serial, time_str)
        
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем")
    except Exception as e:
        print(f"\n❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    main() 