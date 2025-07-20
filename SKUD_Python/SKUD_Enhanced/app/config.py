#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Конфигурация приложения СКУД Enhanced
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

# Загружаем переменные окружения
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = DATA_DIR / "reports"
TEMP_DIR = DATA_DIR / "temp"

# Убеждаемся, что директории существуют
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


class Config:
    """Базовая конфигурация"""
    
    # Безопасность
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
    
    # База данных
    DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR}/skud.db')
    
    # Flask
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID')
    
    # ESP32 API
    ESP32_API_KEY = os.getenv('ESP32_API_KEY', 'default-api-key')
    
    # Уведомления
    DEFAULT_ADMIN_NOTIFICATIONS = os.getenv('DEFAULT_ADMIN_NOTIFICATIONS', 'True').lower() == 'true'
    DEFAULT_EMPLOYEE_NOTIFICATIONS = os.getenv('DEFAULT_EMPLOYEE_NOTIFICATIONS', 'True').lower() == 'true'
    
    # Автозакрытие дней
    AUTO_CLOSE_TIME = os.getenv('AUTO_CLOSE_TIME', '17:00')
    AUTO_CLOSE_ENABLED = os.getenv('AUTO_CLOSE_ENABLED', 'True').lower() == 'true'
    
    # Регистрационные ссылки
    REGISTRATION_LINK_EXPIRE_HOURS = int(os.getenv('REGISTRATION_LINK_EXPIRE_HOURS', 24))
    
    # Веб-интерфейс
    WEB_URL = os.getenv('WEB_URL', 'http://localhost:5000')
    WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:5000/telegram-webapp')
    
    # Логирование
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = LOGS_DIR / os.getenv('LOG_FILE', 'skud.log')
    LOG_MAX_SIZE = os.getenv('LOG_MAX_SIZE', '10MB')
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # Директории
    DATA_DIR = DATA_DIR
    LOGS_DIR = LOGS_DIR
    REPORTS_DIR = REPORTS_DIR
    TEMP_DIR = TEMP_DIR
    
    @classmethod
    def validate(cls) -> bool:
        """Проверяет, что все необходимые переменные заданы"""
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN не задан")
            
        if not cls.TELEGRAM_ADMIN_ID:
            errors.append("TELEGRAM_ADMIN_ID не задан")
            
        if errors:
            print("❌ Ошибки конфигурации:")
            for error in errors:
                print(f"  - {error}")
            return False
            
        return True


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    FLASK_DEBUG = True


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    FLASK_DEBUG = False


class TestingConfig(Config):
    """Конфигурация для тестирования"""
    TESTING = True
    DATABASE_URL = f'sqlite:///{DATA_DIR}/test_skud.db'


# Выбор конфигурации на основе переменной окружения
config_mode = os.getenv('FLASK_ENV', 'development').lower()

if config_mode == 'production':
    config = ProductionConfig
elif config_mode == 'testing':
    config = TestingConfig
else:
    config = DevelopmentConfig 