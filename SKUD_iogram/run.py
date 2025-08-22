#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Главный скрипт для запуска СКУД бота на aiogram
"""

import asyncio
import logging
import os
import sys

# Добавляем текущую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import main

if __name__ == '__main__':
    print("🚀 Запуск СКУД бота на aiogram...")
    print("📱 Тестовый токен: 8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM")
    print("🌐 Для локального тестирования")
    print("📝 Логи сохраняются в telegram_bot.log")
    print("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        logging.error(f"Критическая ошибка: {e}")
        sys.exit(1)
