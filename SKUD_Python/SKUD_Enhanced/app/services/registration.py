#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Сервис для регистрации сотрудников через ссылки
"""

import secrets
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from ..config import config
from ..models import RegistrationRequest, Employee, RFIDCard, UserRole


class RegistrationService:
    """Сервис для управления регистрацией сотрудников"""
    
    def __init__(self):
        self.secret_key = config.JWT_SECRET_KEY
        self.algorithm = config.JWT_ALGORITHM
        self.expire_hours = config.REGISTRATION_LINK_EXPIRE_HOURS
    
    async def create_registration_link(self, db: Session, card_serial: str) -> str:
        """
        Создает ссылку для регистрации сотрудника
        
        Args:
            db: Сессия базы данных
            card_serial: Серийный номер карты
            
        Returns:
            URL для регистрации
        """
        try:
            # Генерируем уникальный токен
            token = self._generate_token()
            
            # Создаем запись в базе данных
            expires_at = datetime.now(timezone.utc) + timedelta(hours=self.expire_hours)
            
            registration_request = RegistrationRequest(
                token=token,
                card_serial=card_serial.upper(),
                expires_at=expires_at
            )
            
            db.add(registration_request)
            db.commit()
            
            # Формируем URL
            registration_url = f"{config.WEB_URL}/register/{token}"
            
            logger.info(f"Создана ссылка регистрации для карты {card_serial}: {token[:8]}...")
            return registration_url
            
        except Exception as e:
            logger.error(f"Ошибка создания ссылки регистрации: {e}")
            raise
    
    def _generate_token(self) -> str:
        """Генерирует безопасный токен"""
        return secrets.token_urlsafe(32)
    
    async def validate_registration_token(self, db: Session, token: str) -> Optional[RegistrationRequest]:
        """
        Проверяет валидность токена регистрации
        
        Args:
            db: Сессия базы данных
            token: Токен регистрации
            
        Returns:
            Объект запроса регистрации или None
        """
        try:
            request = db.query(RegistrationRequest).filter(
                RegistrationRequest.token == token
            ).first()
            
            if not request:
                logger.warning(f"Токен регистрации не найден: {token[:8]}...")
                return None
            
            if not request.is_valid:
                logger.warning(f"Токен регистрации недействителен: {token[:8]}...")
                return None
            
            return request
            
        except Exception as e:
            logger.error(f"Ошибка валидации токена: {e}")
            return None
    
    async def complete_registration(
        self, 
        db: Session, 
        token: str, 
        employee_name: str,
        telegram_id: str = None,
        telegram_username: str = None,
        user_agent: str = None,
        ip_address: str = None
    ) -> tuple[bool, str, Optional[Employee]]:
        """
        Завершает регистрацию сотрудника
        
        Args:
            db: Сессия базы данных
            token: Токен регистрации
            employee_name: Имя сотрудника
            telegram_id: ID пользователя Telegram
            telegram_username: Username пользователя Telegram
            user_agent: User-Agent браузера
            ip_address: IP адрес
            
        Returns:
            Tuple[success, message, employee]
        """
        try:
            # Проверяем токен
            request = await self.validate_registration_token(db, token)
            if not request:
                return False, "Недействительная или просроченная ссылка", None
            
            # Проверяем, не существует ли уже карта
            existing_card = db.query(RFIDCard).filter(
                RFIDCard.serial_number == request.card_serial,
                RFIDCard.is_active == True
            ).first()
            
            if existing_card and existing_card.employee_id:
                return False, "Карта уже зарегистрирована на другого сотрудника", None
            
            # Проверяем, не зарегистрирован ли уже пользователь Telegram
            if telegram_id:
                existing_employee = db.query(Employee).filter(
                    Employee.telegram_id == telegram_id
                ).first()
                
                if existing_employee:
                    return False, "Этот Telegram аккаунт уже зарегистрирован", None
            
            # Создаем сотрудника
            employee = Employee(
                name=employee_name.strip(),
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                role=UserRole.EMPLOYEE,
                notifications_enabled=True,
                arrival_notifications=True,
                departure_notifications=True
            )
            
            db.add(employee)
            db.flush()  # Получаем ID
            
            # Создаем или обновляем карту
            if existing_card:
                # Обновляем существующую карту
                existing_card.employee_id = employee.id
                existing_card.description = f"Карта для {employee_name}"
                card = existing_card
            else:
                # Создаем новую карту
                card = RFIDCard(
                    serial_number=request.card_serial,
                    employee_id=employee.id,
                    card_type="MIFARE",
                    description=f"Карта для {employee_name}"
                )
                db.add(card)
            
            # Отмечаем запрос как использованный
            request.is_used = True
            request.used_at = datetime.now(timezone.utc)
            request.telegram_id = telegram_id
            request.user_agent = user_agent
            request.ip_address = ip_address
            
            # Если есть employee_id в запросе, связываем
            if not request.employee_id:
                request.employee_id = employee.id
            
            db.commit()
            
            logger.info(f"Регистрация завершена: {employee_name} с картой {request.card_serial}")
            return True, "Регистрация успешно завершена", employee
            
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка завершения регистрации: {e}")
            return False, f"Ошибка регистрации: {str(e)}", None
    
    async def get_registration_info(self, db: Session, token: str) -> Optional[dict]:
        """
        Получает информацию о регистрации по токену
        
        Args:
            db: Сессия базы данных
            token: Токен регистрации
            
        Returns:
            Словарь с информацией о регистрации
        """
        try:
            request = await self.validate_registration_token(db, token)
            if not request:
                return None
            
            return {
                'card_serial': request.card_serial,
                'expires_at': request.expires_at,
                'created_at': request.created_at,
                'is_valid': request.is_valid,
                'hours_left': (request.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о регистрации: {e}")
            return None
    
    async def cleanup_expired_requests(self, db: Session) -> int:
        """
        Удаляет просроченные запросы регистрации
        
        Returns:
            Количество удаленных записей
        """
        try:
            now = datetime.now(timezone.utc)
            
            # Помечаем просроченные запросы
            expired_count = db.query(RegistrationRequest).filter(
                RegistrationRequest.expires_at < now,
                RegistrationRequest.is_expired == False
            ).update({'is_expired': True})
            
            # Удаляем старые просроченные запросы (старше 7 дней)
            week_ago = now - timedelta(days=7)
            deleted_count = db.query(RegistrationRequest).filter(
                RegistrationRequest.expires_at < week_ago,
                RegistrationRequest.is_expired == True
            ).delete()
            
            db.commit()
            
            if expired_count > 0:
                logger.info(f"Помечено как просроченные: {expired_count} запросов")
            
            if deleted_count > 0:
                logger.info(f"Удалено старых запросов: {deleted_count}")
            
            return expired_count + deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки просроченных запросов: {e}")
            return 0
    
    async def get_active_requests(self, db: Session) -> list:
        """
        Получает список активных запросов регистрации
        
        Returns:
            Список активных запросов
        """
        try:
            requests = db.query(RegistrationRequest).filter(
                RegistrationRequest.is_used == False,
                RegistrationRequest.is_expired == False,
                RegistrationRequest.expires_at > datetime.now(timezone.utc)
            ).order_by(RegistrationRequest.created_at.desc()).all()
            
            result = []
            for req in requests:
                result.append({
                    'id': req.id,
                    'token': req.token[:8] + '...',
                    'card_serial': req.card_serial,
                    'created_at': req.created_at,
                    'expires_at': req.expires_at,
                    'hours_left': (req.expires_at - datetime.now(timezone.utc)).total_seconds() / 3600
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения активных запросов: {e}")
            return []
    
    async def revoke_registration_request(self, db: Session, token: str) -> bool:
        """
        Отзывает запрос регистрации
        
        Args:
            db: Сессия базы данных
            token: Токен запроса
            
        Returns:
            True если успешно отозван
        """
        try:
            request = db.query(RegistrationRequest).filter(
                RegistrationRequest.token == token
            ).first()
            
            if not request:
                return False
            
            request.is_expired = True
            db.commit()
            
            logger.info(f"Запрос регистрации отозван: {token[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отзыва запроса регистрации: {e}")
            return False 