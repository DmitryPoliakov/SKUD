#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from dataclasses import dataclass

@dataclass
class Config:
    """Конфигурация бота"""
    
    # Токен Telegram бота
    TELEGRAM_TOKEN: str = "7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY"
    # 7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY
    # 8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM тестовый
    
    # Список разрешенных пользователей (ID)
    ALLOWED_USERS: list = None
    
    # ID администратора для уведомлений (из оригинала)
    ADMIN_USER_ID: int = 42291783
    
    # URL веб-приложения
    WEBAPP_URL: str = "https://skud-ek.ru/telegram-reports?tgWebApp=1"
    
    # Пути к файлам данных
    DATA_DIR: str = "data"
    ATTENDANCE_FILE: str = "data/attendance.csv"
    EMPLOYEES_FILE: str = "data/employees.json"
    REPORTS_DIR: str = "data/reports"
    
    def __post_init__(self):
        """Создание директорий при инициализации"""
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.REPORTS_DIR, exist_ok=True)
        
        # Если не указаны разрешенные пользователи, добавляем администратора
        if self.ALLOWED_USERS is None:
            self.ALLOWED_USERS = [self.ADMIN_USER_ID] if self.ADMIN_USER_ID else []
            
        # Инициализация менеджера уведомлений
        self._init_notifications()
    
    def _init_notifications(self):
        """Инициализация системы уведомлений"""
        try:
            from utils.notifications import notification_manager
            notification_manager.initialize(
                bot_token=self.TELEGRAM_TOKEN,
                allowed_users=self.ALLOWED_USERS,
                admin_user_id=self.ADMIN_USER_ID
            )
        except ImportError:
            # Модуль уведомлений не найден, продолжаем без него
            pass

# Глобальный экземпляр конфигурации
config = Config()
