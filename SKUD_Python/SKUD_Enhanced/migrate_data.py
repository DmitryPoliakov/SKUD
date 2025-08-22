#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт миграции данных из старой системы СКУД в новую Enhanced версию
"""

import os
import sys
from pathlib import Path

# Добавляем путь к приложению
sys.path.insert(0, str(Path(__file__).parent))

from app.database import migrate_from_legacy_system
from loguru import logger


def main():
    """Главная функция миграции"""
    try:
        logger.info("Запуск миграции данных из старой системы СКУД")
        
        # Путь к данным старой системы
        legacy_data_dir = "../data"  # Относительно новой системы
        
        # Проверяем, существует ли папка со старыми данными
        legacy_path = Path(legacy_data_dir)
        if not legacy_path.exists():
            logger.error(f"Папка со старыми данными не найдена: {legacy_path.absolute()}")
            logger.info("Убедитесь, что старые данные находятся в ../data/ относительно новой системы")
            return False
        
        # Запускаем миграцию
        success = migrate_from_legacy_system(legacy_data_dir)
        
        if success:
            logger.success("✅ Миграция данных завершена успешно!")
            logger.info("Проверьте логи выше для подробной информации")
        else:
            logger.error("❌ Миграция данных завершилась с ошибками")
        
        return success
        
    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 