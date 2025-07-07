#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import threading
import time
import schedule
from subprocess import Popen
from pathlib import Path

# Настройка путей
BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = BASE_DIR / "data"

# Убедимся, что директории существуют
os.makedirs(DATA_DIR, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / 'skud.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Добавляем текущий каталог в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Функция для запуска Flask API
def run_flask_api():
    logger.info("Запуск Flask API...")
    flask_process = Popen([sys.executable, "-m", "app.main"], cwd=APP_DIR.parent)
    return flask_process

# Функция для запуска Telegram бота
def run_telegram_bot():
    logger.info("Запуск Telegram бота...")
    bot_process = Popen([sys.executable, str(APP_DIR / "telegram_bot.py")])
    return bot_process

# Функция для запуска автоматического закрытия дней
def run_auto_close():
    logger.info("Запуск автоматического закрытия незавершенных дней...")
    os.system(f"{sys.executable} {APP_DIR / 'auto_close.py'}")

# Функция для планирования задач
def run_scheduler():
    # Запускаем автоматическое закрытие дней каждый день в 00:01
    schedule.every().day.at("00:01").do(run_auto_close)
    
    logger.info("Планировщик задач запущен")
    while True:
        schedule.run_pending()
        time.sleep(60)

# Главная функция
def main():
    logger.info("Запуск системы СКУД")
    
    try:
        # Импортируем веб-маршруты
        # Закомментируем импорт, так как маршруты уже определены в main.py
        # import app.web_routes
        
        # Запускаем Flask API
        flask_process = run_flask_api()
        
        # Запускаем Telegram бота
        bot_process = run_telegram_bot()
        
        # Запускаем планировщик в отдельном потоке
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        logger.info("Все компоненты системы СКУД запущены")
        logger.info(f"Веб-интерфейс доступен по адресу: http://localhost:5000")
        
        # Ждем завершения процессов
        flask_process.wait()
        bot_process.wait()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал завершения работы")
    except Exception as e:
        logger.exception(f"Произошла ошибка: {str(e)}")
    finally:
        logger.info("Завершение работы системы СКУД")
        sys.exit(0)

if __name__ == "__main__":
    main() 