#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модуль для отправки уведомлений в Telegram
Используется как API сервером, так и ботом
"""

import asyncio
import logging
import os
import json
from datetime import datetime
from typing import Optional, List
import aiohttp

logger = logging.getLogger(__name__)

class NotificationManager:
    """Менеджер уведомлений для СКУД"""
    
    def __init__(self):
        self.bot_token: Optional[str] = None
        self.allowed_users: List[int] = []
        self.admin_user_id: Optional[int] = None
        
    def initialize(self, bot_token: str, allowed_users: List[int] = None, admin_user_id: int = None):
        """Инициализация менеджера уведомлений"""
        self.bot_token = bot_token
        self.allowed_users = allowed_users or []
        self.admin_user_id = admin_user_id
        logger.info(f"NotificationManager инициализирован. Админ: {admin_user_id}, Пользователей: {len(self.allowed_users)}")
    
    async def _send_telegram_message(self, chat_id: int, text: str) -> bool:
        """Отправляет сообщение в Telegram через API (исправлено для избежания конфликтов)"""
        if not self.bot_token:
            logger.error("Токен бота не настроен")
            return False
            
        try:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                
                data = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'HTML'
                }
                
                async with session.post(url, data=data) as response:  # Используем data вместо json
                    if response.status == 200:
                        logger.info(f"Уведомление отправлено пользователю {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка отправки уведомления: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Исключение при отправке уведомления: {e}")
            return False
    
    async def send_notification(self, message: str) -> bool:
        """Отправляет уведомление администратору или всем разрешенным пользователям"""
        try:
            if self.admin_user_id:
                # Отправляем админу
                return await self._send_telegram_message(self.admin_user_id, message)
            elif self.allowed_users:
                # Отправляем всем разрешенным пользователям
                success_count = 0
                for user_id in self.allowed_users:
                    if await self._send_telegram_message(user_id, message):
                        success_count += 1
                return success_count > 0
            else:
                logger.warning("Нет настроенных получателей уведомлений")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
            return False
    
    def send_notification_sync(self, message: str):
        """Синхронная версия отправки уведомления для вызова из Flask API"""
        try:
            # Используем синхронные HTTP запросы для избежания проблем с event loop
            import requests
            
            if not self.bot_token:
                logger.error("Токен бота не настроен")
                return False
                
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            # Отправляем всем разрешенным пользователям
            for user_id in self.allowed_users:
                try:
                    data = {
                        'chat_id': user_id,
                        'text': message,
                        'parse_mode': 'HTML'
                    }
                    
                    response = requests.post(url, data=data, timeout=10)
                    
                    if response.status_code == 200:
                        logger.info(f"Уведомление отправлено пользователю {user_id} (sync)")
                    else:
                        logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    logger.error(f"Исключение при отправке уведомления пользователю {user_id}: {e}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Ошибка синхронной отправки уведомления: {e}")
            return False
    
    async def close(self):
        """Закрытие ресурсов (заглушка для совместимости)"""
        pass

# Глобальный экземпляр менеджера уведомлений
notification_manager = NotificationManager()

# Функции для совместимости
async def send_notification(message: str) -> bool:
    """Отправляет уведомление (асинхронно)"""
    return await notification_manager.send_notification(message)

def send_notification_sync(message: str):
    """Отправляет уведомление (синхронно)"""
    notification_manager.send_notification_sync(message)
