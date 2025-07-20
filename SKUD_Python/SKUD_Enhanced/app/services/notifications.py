#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Сервис для отправки уведомлений
"""

from datetime import datetime
from typing import Optional, List
from loguru import logger

from ..models import Employee, AttendanceEvent, EventType


class NotificationService:
    """Сервис для управления уведомлениями"""
    
    def __init__(self, bot=None):
        self.bot = bot
    
    async def send_attendance_notification(
        self, 
        employee: Employee, 
        event: AttendanceEvent, 
        card_serial: str
    ) -> bool:
        """
        Отправляет уведомление сотруднику о посещаемости
        
        Args:
            employee: Сотрудник
            event: Событие посещаемости
            card_serial: Серийный номер карты
            
        Returns:
            True если уведомление отправлено успешно
        """
        try:
            if not self.bot:
                logger.warning("Telegram бот не инициализирован")
                return False
            
            if not employee.telegram_id:
                logger.debug(f"У сотрудника {employee.name} нет Telegram ID")
                return False
            
            # Проверяем настройки уведомлений
            if not employee.notifications_enabled:
                logger.debug(f"Уведомления отключены для {employee.name}")
                return False
            
            # Проверяем конкретный тип уведомления
            if event.event_type == EventType.ARRIVAL and not employee.arrival_notifications:
                logger.debug(f"Уведомления о приходе отключены для {employee.name}")
                return False
            
            if event.event_type == EventType.DEPARTURE and not employee.departure_notifications:
                logger.debug(f"Уведомления об уходе отключены для {employee.name}")
                return False
            
            # Формируем сообщение
            message = self._format_attendance_message(employee, event, card_serial)
            
            # Отправляем уведомление
            await self.bot.send_message(
                chat_id=employee.telegram_id,
                text=message,
                parse_mode='HTML'
            )
            
            logger.info(f"Отправлено уведомление сотруднику {employee.name} ({employee.telegram_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления сотруднику {employee.name}: {e}")
            return False
    
    def _format_attendance_message(
        self, 
        employee: Employee, 
        event: AttendanceEvent, 
        card_serial: str
    ) -> str:
        """Форматирует сообщение о посещаемости"""
        
        # Эмодзи и текст в зависимости от типа события
        if event.event_type == EventType.ARRIVAL:
            emoji = "🟢"
            action = "Приход на работу"
            greeting = f"Добро пожаловать на работу, <b>{employee.name}</b>!"
        else:
            emoji = "🔴"
            action = "Уход с работы"
            greeting = f"Хорошего дня, <b>{employee.name}</b>!"
        
        # Форматируем время
        local_time = event.local_time
        time_str = local_time.strftime('%H:%M')
        date_str = local_time.strftime('%d.%m.%Y')
        
        message = f"{emoji} <b>{action}</b>\n\n"
        message += f"{greeting}\n\n"
        message += f"⏰ Время: <b>{time_str}</b>\n"
        message += f"📅 Дата: {date_str}\n"
        message += f"💳 Карта: <code>{card_serial}</code>"
        
        # Добавляем заметки если есть
        if event.notes:
            message += f"\n📝 Заметка: {event.notes}"
        
        return message
    
    async def send_admin_notification(
        self, 
        admin_id: str, 
        message: str, 
        reply_markup=None
    ) -> bool:
        """
        Отправляет уведомление администратору
        
        Args:
            admin_id: Telegram ID администратора
            message: Текст сообщения
            reply_markup: Клавиатура (опционально)
            
        Returns:
            True если уведомление отправлено успешно
        """
        try:
            if not self.bot:
                logger.warning("Telegram бот не инициализирован")
                return False
            
            await self.bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            logger.info(f"Отправлено уведомление администратору ({admin_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору: {e}")
            return False
    
    async def send_unknown_card_notification(
        self, 
        admin_id: str, 
        card_serial: str, 
        timestamp: datetime,
        reply_markup=None
    ) -> bool:
        """
        Отправляет уведомление о неизвестной карте
        
        Args:
            admin_id: Telegram ID администратора
            card_serial: Серийный номер карты
            timestamp: Время события
            reply_markup: Клавиатура с действиями
            
        Returns:
            True если уведомление отправлено успешно
        """
        try:
            local_time = timestamp.strftime('%d.%m.%Y %H:%M:%S')
            
            message = f"🔴 <b>Обнаружена неизвестная карта</b>\n\n"
            message += f"💳 Серийный номер: <code>{card_serial}</code>\n"
            message += f"⏰ Время: {local_time}\n\n"
            message += f"Выберите действие:"
            
            return await self.send_admin_notification(admin_id, message, reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о неизвестной карте: {e}")
            return False
    
    async def send_system_notification(
        self, 
        admin_id: str, 
        title: str, 
        details: str, 
        level: str = "INFO"
    ) -> bool:
        """
        Отправляет системное уведомление
        
        Args:
            admin_id: Telegram ID администратора
            title: Заголовок уведомления
            details: Детали уведомления
            level: Уровень важности (INFO, WARNING, ERROR)
            
        Returns:
            True если уведомление отправлено успешно
        """
        try:
            # Эмодзи в зависимости от уровня
            emoji_map = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "🚨",
                "SUCCESS": "✅"
            }
            
            emoji = emoji_map.get(level, "📋")
            
            message = f"{emoji} <b>{title}</b>\n\n"
            message += details
            message += f"\n\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            
            return await self.send_admin_notification(admin_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка отправки системного уведомления: {e}")
            return False
    
    async def send_bulk_notification(
        self, 
        employee_ids: List[str], 
        message: str
    ) -> dict:
        """
        Отправляет массовое уведомление сотрудникам
        
        Args:
            employee_ids: Список Telegram ID сотрудников
            message: Текст сообщения
            
        Returns:
            Словарь со статистикой отправки
        """
        try:
            if not self.bot:
                logger.warning("Telegram бот не инициализирован")
                return {"success": 0, "failed": len(employee_ids)}
            
            success_count = 0
            failed_count = 0
            
            for employee_id in employee_ids:
                try:
                    await self.bot.send_message(
                        chat_id=employee_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    success_count += 1
                    
                except Exception as e:
                    logger.warning(f"Не удалось отправить сообщение {employee_id}: {e}")
                    failed_count += 1
            
            logger.info(f"Массовая рассылка: {success_count} успешно, {failed_count} неудач")
            
            return {
                "success": success_count,
                "failed": failed_count,
                "total": len(employee_ids)
            }
            
        except Exception as e:
            logger.error(f"Ошибка массовой рассылки: {e}")
            return {"success": 0, "failed": len(employee_ids), "error": str(e)}
    
    async def send_report_notification(
        self, 
        employee_id: str, 
        report_name: str, 
        report_path: str = None
    ) -> bool:
        """
        Отправляет уведомление о готовности отчета
        
        Args:
            employee_id: Telegram ID сотрудника
            report_name: Название отчета
            report_path: Путь к файлу отчета (опционально)
            
        Returns:
            True если уведомление отправлено успешно
        """
        try:
            if not self.bot:
                return False
            
            message = f"📊 <b>Отчет готов</b>\n\n"
            message += f"📋 Название: {report_name}\n"
            message += f"🕐 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            if report_path:
                # Отправляем файл
                with open(report_path, 'rb') as file:
                    await self.bot.send_document(
                        chat_id=employee_id,
                        document=file,
                        caption=message,
                        parse_mode='HTML'
                    )
            else:
                # Отправляем только текст
                await self.bot.send_message(
                    chat_id=employee_id,
                    text=message,
                    parse_mode='HTML'
                )
            
            logger.info(f"Отправлено уведомление о отчете: {report_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о отчете: {e}")
            return False 