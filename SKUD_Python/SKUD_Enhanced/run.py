#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Главный файл запуска системы СКУД Enhanced
Запускает Flask API, Telegram бота и планировщик задач
"""

import asyncio
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from datetime import datetime
from loguru import logger

from app.config import config
from app.database import init_database, create_initial_data
from app.telegram_bot import start_bot, stop_bot
from app.main import create_app
from app.services.attendance import AttendanceService


class SKUDSystem:
    """Основной класс системы СКУД Enhanced"""
    
    def __init__(self):
        self.flask_app = None
        self.flask_thread = None
        self.bot_task = None
        self.scheduler_task = None
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.running = False
        
        # Сервисы
        self.attendance_service = AttendanceService()
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        asyncio.create_task(self.stop())
    
    async def start(self):
        """Запуск всей системы"""
        try:
            logger.info("🚀 Запуск системы СКУД Enhanced...")
            
            # Проверяем конфигурацию
            if not config.validate():
                raise Exception("Ошибка конфигурации системы")
            
            # Инициализируем базу данных
            logger.info("📊 Инициализация базы данных...")
            init_database()
            create_initial_data()
            
            # Запускаем Flask приложение
            logger.info("🌐 Запуск Flask API...")
            await self._start_flask()
            
            # Запускаем Telegram бота
            logger.info("🤖 Запуск Telegram бота...")
            self.bot_task = asyncio.create_task(start_bot())
            
            # Запускаем планировщик
            logger.info("⏰ Запуск планировщика задач...")
            self.scheduler_task = asyncio.create_task(self._run_scheduler())
            
            self.running = True
            logger.success("✅ Система СКУД Enhanced успешно запущена!")
            
            # Выводим информацию о системе
            self._print_system_info()
            
            # Ожидаем завершения
            try:
                await asyncio.gather(
                    self.bot_task,
                    self.scheduler_task,
                    return_exceptions=True
                )
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка запуска системы: {e}")
            await self.stop()
            raise
    
    async def _start_flask(self):
        """Запуск Flask приложения в отдельном потоке"""
        try:
            self.flask_app = create_app()
            
            def run_flask():
                self.flask_app.run(
                    host=config.FLASK_HOST,
                    port=config.FLASK_PORT,
                    debug=False,  # Отключаем debug в многопоточном режиме
                    use_reloader=False,
                    threaded=True
                )
            
            self.flask_thread = Thread(target=run_flask, daemon=True)
            self.flask_thread.start()
            
            # Даем время Flask для запуска
            await asyncio.sleep(2)
            
            logger.success(f"Flask API запущен на http://{config.FLASK_HOST}:{config.FLASK_PORT}")
            
        except Exception as e:
            logger.error(f"Ошибка запуска Flask: {e}")
            raise
    
    async def _run_scheduler(self):
        """Планировщик фоновых задач"""
        try:
            logger.info("Планировщик задач запущен")
            
            last_auto_close_date = None
            last_cleanup_hour = None
            
            while self.running:
                try:
                    now = datetime.now()
                    
                    # Автозакрытие дней в 00:01
                    if (config.AUTO_CLOSE_ENABLED and 
                        now.hour == 0 and now.minute <= 5 and 
                        now.strftime('%Y-%m-%d') != last_auto_close_date):
                        
                        logger.info("Выполняется автозакрытие дней...")
                        
                        from app.database import get_db
                        with next(get_db()) as db:
                            closed_count = await self.attendance_service.auto_close_day(db)
                            if closed_count > 0:
                                logger.info(f"Автоматически закрыто {closed_count} дней")
                        
                        last_auto_close_date = now.strftime('%Y-%m-%d')
                    
                    # Очистка просроченных запросов регистрации каждый час
                    if now.minute == 0 and now.hour != last_cleanup_hour:
                        logger.info("Очистка просроченных запросов регистрации...")
                        
                        from app.services.registration import RegistrationService
                        from app.database import get_db
                        
                        reg_service = RegistrationService()
                        with next(get_db()) as db:
                            cleaned_count = await reg_service.cleanup_expired_requests(db)
                            if cleaned_count > 0:
                                logger.info(f"Очищено {cleaned_count} просроченных запросов")
                        
                        last_cleanup_hour = now.hour
                    
                    # Спим 30 секунд
                    await asyncio.sleep(30)
                    
                except Exception as e:
                    logger.error(f"Ошибка в планировщике: {e}")
                    await asyncio.sleep(60)  # Увеличиваем интервал при ошибках
            
        except asyncio.CancelledError:
            logger.info("Планировщик остановлен")
        except Exception as e:
            logger.error(f"Критическая ошибка планировщика: {e}")
    
    def _print_system_info(self):
        """Выводит информацию о запущенной системе"""
        print("\n" + "="*60)
        print("📋 СИСТЕМА СКУД ENHANCED ЗАПУЩЕНА")
        print("="*60)
        print(f"🌐 Web-интерфейс: http://{config.FLASK_HOST}:{config.FLASK_PORT}")
        print(f"🤖 Telegram бот: {'Активен' if config.TELEGRAM_BOT_TOKEN else 'Не настроен'}")
        print(f"👨‍💼 Администратор: {config.TELEGRAM_ADMIN_ID if config.TELEGRAM_ADMIN_ID else 'Не настроен'}")
        print(f"💾 База данных: {config.DATABASE_URL}")
        print(f"📁 Данные: {config.DATA_DIR}")
        print(f"📊 Отчеты: {config.REPORTS_DIR}")
        print(f"📝 Логи: {config.LOGS_DIR}")
        print("="*60)
        print("🔄 Система готова к работе!")
        print("📱 Для остановки нажмите Ctrl+C")
        print("="*60 + "\n")
    
    async def stop(self):
        """Остановка всей системы"""
        if not self.running:
            return
        
        logger.info("⏹️ Остановка системы СКУД Enhanced...")
        self.running = False
        
        try:
            # Останавливаем Telegram бота
            if self.bot_task and not self.bot_task.done():
                logger.info("Остановка Telegram бота...")
                await stop_bot()
                self.bot_task.cancel()
                try:
                    await self.bot_task
                except asyncio.CancelledError:
                    pass
            
            # Останавливаем планировщик
            if self.scheduler_task and not self.scheduler_task.done():
                logger.info("Остановка планировщика...")
                self.scheduler_task.cancel()
                try:
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass
            
            # Останавливаем Flask (он останется работать в фоновом потоке)
            if self.flask_thread and self.flask_thread.is_alive():
                logger.info("Flask приложение продолжит работу...")
            
            # Закрываем executor
            self.executor.shutdown(wait=True)
            
            logger.success("✅ Система СКУД Enhanced остановлена")
            
        except Exception as e:
            logger.error(f"Ошибка при остановке системы: {e}")


# Дополнительные функции для управления

def init_system():
    """Инициализация системы без запуска"""
    try:
        logger.info("Инициализация системы СКУД Enhanced...")
        
        # Проверяем конфигурацию
        if not config.validate():
            logger.error("Ошибка конфигурации")
            return False
        
        # Инициализируем базу данных
        init_database()
        create_initial_data()
        
        logger.success("Система успешно инициализирована")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации: {e}")
        return False


def run_flask_only():
    """Запуск только Flask приложения"""
    try:
        logger.info("Запуск только Flask API...")
        
        if not init_system():
            return
        
        app = create_app()
        logger.success(f"Flask API запущен на http://{config.FLASK_HOST}:{config.FLASK_PORT}")
        
        app.run(
            host=config.FLASK_HOST,
            port=config.FLASK_PORT,
            debug=config.FLASK_DEBUG
        )
        
    except Exception as e:
        logger.error(f"Ошибка запуска Flask: {e}")


def run_bot_only():
    """Запуск только Telegram бота"""
    try:
        logger.info("Запуск только Telegram бота...")
        
        if not init_system():
            return
        
        asyncio.run(start_bot())
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")


async def main():
    """Основная функция"""
    system = SKUDSystem()
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await system.stop()


if __name__ == "__main__":
    # Настройка логирования
    logger.remove()  # Удаляем стандартный обработчик
    
    # Добавляем обработчик в консоль
    logger.add(
        sys.stderr,
        level=config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )
    
    # Добавляем обработчик в файл
    logger.add(
        config.LOG_FILE,
        level=config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "init":
            init_system()
        elif command == "flask":
            run_flask_only()
        elif command == "bot":
            run_bot_only()
        elif command == "help":
            print("""
Использование: python run.py [команда]

Команды:
  (пусто)  - Запуск всей системы (Flask + Telegram бот + планировщик)
  init     - Только инициализация базы данных
  flask    - Запуск только Flask API
  bot      - Запуск только Telegram бота
  help     - Показать эту справку

Примеры:
  python run.py          # Полный запуск
  python run.py flask    # Только веб-сервер
  python run.py bot      # Только бот
            """)
        else:
            logger.error(f"Неизвестная команда: {command}")
            logger.info("Используйте 'python run.py help' для справки")
    else:
        # Запуск всей системы
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Завершение работы...")
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            sys.exit(1) 