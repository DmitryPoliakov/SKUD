#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Оптимизированный запуск СКУД бота для продакшн сервера
Минимальная нагрузка на CPU при старте
"""

import asyncio
import logging
import os
import sys
import signal
import time

# Настройка логирования для продакшена
logging.basicConfig(
    level=logging.INFO,  # Только INFO и выше
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)

# Отключаем избыточное логирование pandas и matplotlib
logging.getLogger('matplotlib').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Добавляем текущую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Глобальная переменная для graceful shutdown
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Получен сигнал {signum}, начинаем остановку бота...")
    shutdown_event.set()

async def main():
    """Главная функция с оптимизацией для продакшена"""
    logger.info("🚀 Запуск СКУД бота (оптимизированная версия)")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Импортируем бот только после настройки логирования
        from bot import bot, dp
        
        # Быстрая проверка конфигурации без загрузки данных
        from config import config
        logger.info(f"Токен настроен: {'Да' if config.TELEGRAM_TOKEN else 'Нет'}")
        logger.info(f"Админ настроен: {'Да' if config.ADMIN_USER_ID else 'Нет'}")
        
        # Запуск polling с обработкой shutdown
        polling_task = asyncio.create_task(dp.start_polling(bot))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        
        # Ждем либо завершения polling, либо сигнала shutdown
        done, pending = await asyncio.wait(
            [polling_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Отменяем незавершенные задачи
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        logger.info("✅ Бот остановлен корректно")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        # Закрываем сессии уведомлений
        try:
            from utils.notifications import notification_manager
            await notification_manager.close()
        except:
            pass

if __name__ == '__main__':
    # Проверяем Python версию
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    print("🔧 Режим: Продакшн")
    print("📝 Логи: telegram_bot.log")
    print("🛑 Остановка: Ctrl+C или SIGTERM")
    print("=" * 50)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем")
    except Exception as e:
        print(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)
