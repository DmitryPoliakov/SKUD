#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для симуляции запросов от ESP32 считывателя
Проверяет работу уведомлений и записи данных
"""

import requests
import json
from datetime import datetime

def test_esp32_request(serial, employee_name=""):
    """Симулирует запрос от ESP32 считывателя"""
    
    # URL API сервера
    url = "http://localhost:5000/api/attendance"
    
    # Текущее время
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Данные для отправки (как от ESP32)
    data = {
        "serial": serial,
        "time": current_time
    }
    
    print(f"🔄 Отправка тестового запроса от ESP32...")
    print(f"📡 URL: {url}")
    print(f"📋 Данные: {json.dumps(data, indent=2, ensure_ascii=False)}")
    print(f"👤 Ожидается сотрудник: {employee_name}")
    print("-" * 50)
    
    try:
        # Отправляем POST запрос
        response = requests.post(url, json=data, timeout=10)
        
        print(f"📥 Ответ сервера:")
        print(f"🔢 Статус код: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print(f"✅ Успех: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            print(f"👤 Сотрудник: {response_data.get('employee', 'Неизвестно')}")
            print(f"⏰ Событие: {response_data.get('event', 'Неизвестно')}")
            print(f"🕐 Время: {response_data.get('time', 'Неизвестно')}")
        else:
            print(f"❌ Ошибка: {response.text}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка подключения к серверу. Убедитесь, что api_server.py запущен на порту 5000")
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
    
    print("=" * 50)
    print()

def main():
    """Основная функция тестирования"""
    print("🔧 Тестирование системы СКУД - симуляция ESP32")
    print("=" * 50)
    print()
    
    # Тестовые карты из employees.json
    test_cards = [
        ("894046B8", "Тарасов Никита"),
        ("97D3A7DD", "Палкин Семён"),
        ("992BEE97", "Поляков Павел"),
        ("UNKNOWN123", "Неизвестная карта")  # Тестируем неизвестную карту
    ]
    
    for serial, name in test_cards:
        test_esp32_request(serial, name)
        
        # Пауза между запросами
        input("Нажмите Enter для следующего теста...")
    
    print("✅ Тестирование завершено!")
    print()
    print("📋 Инструкции:")
    print("1. Проверьте логи в api.log")
    print("2. Проверьте уведомления в Telegram боте") 
    print("3. Проверьте данные в data/attendance.csv")
    print("4. Для настройки уведомлений сотрудникам отредактируйте data/employee_telegram.json")

if __name__ == '__main__':
    main()
