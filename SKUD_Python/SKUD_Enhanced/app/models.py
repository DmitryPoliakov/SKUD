#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Модели базы данных для системы СКУД Enhanced
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, 
    ForeignKey, Text, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
import pytz

Base = declarative_base()


class UserRole(str, Enum):
    """Роли пользователей в системе"""
    ADMIN = "admin"
    EMPLOYEE = "employee"
    VIEWER = "viewer"


class EventType(str, Enum):
    """Типы событий посещаемости"""
    ARRIVAL = "arrival"      # Приход
    DEPARTURE = "departure"  # Уход
    UNKNOWN = "unknown"      # Неизвестная карта


class NotificationType(str, Enum):
    """Типы уведомлений"""
    ATTENDANCE = "attendance"        # Уведомления о посещаемости
    UNKNOWN_CARD = "unknown_card"    # Уведомления о неизвестных картах
    SYSTEM = "system"                # Системные уведомления


class Employee(Base):
    """Модель сотрудника"""
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    telegram_id = Column(String(50), unique=True, nullable=True, index=True)
    telegram_username = Column(String(100), nullable=True)
    
    # Настройки уведомлений
    notifications_enabled = Column(Boolean, default=True)
    arrival_notifications = Column(Boolean, default=True)
    departure_notifications = Column(Boolean, default=True)
    
    # Роль пользователя
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE)
    
    # Активность
    is_active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    cards = relationship("RFIDCard", back_populates="employee", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceEvent", back_populates="employee")
    registration_requests = relationship("RegistrationRequest", back_populates="employee")
    
    def __repr__(self):
        return f"<Employee(id={self.id}, name='{self.name}', telegram_id='{self.telegram_id}')>"
    
    @property
    def is_admin(self) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return self.role == UserRole.ADMIN
    
    def get_active_cards(self) -> List["RFIDCard"]:
        """Возвращает список активных карт сотрудника"""
        return [card for card in self.cards if card.is_active]


class RFIDCard(Base):
    """Модель RFID карты"""
    __tablename__ = "rfid_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(50), unique=True, nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # Информация о карте
    card_type = Column(String(50), default="MIFARE")
    description = Column(Text, nullable=True)
    
    # Активность
    is_active = Column(Boolean, default=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    employee = relationship("Employee", back_populates="cards")
    attendance_events = relationship("AttendanceEvent", back_populates="card")
    
    def __repr__(self):
        return f"<RFIDCard(serial='{self.serial_number}', employee_id={self.employee_id})>"
    
    def update_last_used(self):
        """Обновляет время последнего использования карты"""
        self.last_used_at = datetime.now(timezone.utc)


class AttendanceEvent(Base):
    """Модель события посещаемости"""
    __tablename__ = "attendance_events"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("rfid_cards.id"), nullable=False)
    
    # Информация о событии
    event_type = Column(SQLEnum(EventType), nullable=False)
    event_time = Column(DateTime(timezone=True), nullable=False, index=True)
    event_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD для быстрых запросов
    
    # Дополнительная информация
    notes = Column(Text, nullable=True)
    is_manual = Column(Boolean, default=False)  # Ручное добавление администратором
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    employee = relationship("Employee", back_populates="attendance_records")
    card = relationship("RFIDCard", back_populates="attendance_events")
    
    # Индексы для оптимизации запросов
    __table_args__ = (
        Index('idx_employee_date', 'employee_id', 'event_date'),
        Index('idx_event_time', 'event_time'),
        Index('idx_employee_time', 'employee_id', 'event_time'),
    )
    
    def __repr__(self):
        return f"<AttendanceEvent(employee_id={self.employee_id}, type={self.event_type}, time={self.event_time})>"
    
    @property
    def local_time(self) -> datetime:
        """Возвращает время события в местном часовом поясе"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        if self.event_time.tzinfo is None:
            return moscow_tz.localize(self.event_time)
        return self.event_time.astimezone(moscow_tz)


class DailyAttendance(Base):
    """Модель дневной посещаемости (агрегированные данные)"""
    __tablename__ = "daily_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    
    # Времена прихода и ухода
    arrival_time = Column(DateTime(timezone=True), nullable=True)
    departure_time = Column(DateTime(timezone=True), nullable=True)
    
    # Вычисляемые поля
    hours_worked = Column(Integer, nullable=True)  # В минутах
    is_weekend = Column(Boolean, default=False)
    is_holiday = Column(Boolean, default=False)
    
    # Статус дня
    is_closed = Column(Boolean, default=False)  # Закрыт автоматически или вручную
    auto_closed = Column(Boolean, default=False)  # Закрыт автоматически
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Связи
    employee = relationship("Employee")
    
    # Уникальность по сотруднику и дате
    __table_args__ = (
        UniqueConstraint('employee_id', 'date', name='unique_employee_date'),
        Index('idx_date', 'date'),
        Index('idx_employee_date_daily', 'employee_id', 'date'),
    )
    
    def __repr__(self):
        return f"<DailyAttendance(employee_id={self.employee_id}, date={self.date})>"
    
    @property
    def duration_formatted(self) -> str:
        """Возвращает продолжительность работы в формате HH:MM"""
        if self.hours_worked is None:
            return "—"
        hours = self.hours_worked // 60
        minutes = self.hours_worked % 60
        return f"{hours:02d}:{minutes:02d}"


class RegistrationRequest(Base):
    """Модель запроса на регистрацию сотрудника"""
    __tablename__ = "registration_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    card_serial = Column(String(50), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # Статус запроса
    is_used = Column(Boolean, default=False)
    is_expired = Column(Boolean, default=False)
    
    # Временные ограничения
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Дополнительная информация
    telegram_id = Column(String(50), nullable=True)  # ID того, кто использовал ссылку
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Связи
    employee = relationship("Employee", back_populates="registration_requests")
    
    def __repr__(self):
        return f"<RegistrationRequest(token={self.token[:8]}..., card_serial={self.card_serial})>"
    
    @property
    def is_valid(self) -> bool:
        """Проверяет, действителен ли запрос"""
        now = datetime.now(timezone.utc)
        return not self.is_used and not self.is_expired and self.expires_at > now


class SystemLog(Base):
    """Модель системного лога"""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(10), nullable=False, index=True)  # INFO, WARNING, ERROR, DEBUG
    module = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    
    # Связанные объекты
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("rfid_cards.id"), nullable=True)
    
    # Дополнительные данные
    extra_data = Column(Text, nullable=True)  # JSON строка
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Связи
    employee = relationship("Employee")
    card = relationship("RFIDCard")
    
    def __repr__(self):
        return f"<SystemLog(level={self.level}, module={self.module}, action={self.action})>"


# Утилитарные функции для работы с моделями

def get_or_create_employee(db: Session, telegram_id: str) -> Employee:
    """Получает или создает сотрудника по Telegram ID"""
    employee = db.query(Employee).filter(Employee.telegram_id == telegram_id).first()
    if not employee:
        employee = Employee(
            name=f"Пользователь {telegram_id}",
            telegram_id=telegram_id,
            role=UserRole.EMPLOYEE
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)
    return employee


def get_card_by_serial(db: Session, serial_number: str) -> Optional[RFIDCard]:
    """Получает карту по серийному номеру"""
    return db.query(RFIDCard).filter(
        RFIDCard.serial_number == serial_number,
        RFIDCard.is_active == True
    ).first()


def create_attendance_event(
    db: Session, 
    card: RFIDCard, 
    event_type: EventType, 
    event_time: datetime,
    notes: str = None,
    is_manual: bool = False
) -> AttendanceEvent:
    """Создает событие посещаемости"""
    event_date = event_time.strftime('%Y-%m-%d')
    
    event = AttendanceEvent(
        employee_id=card.employee_id,
        card_id=card.id,
        event_type=event_type,
        event_time=event_time,
        event_date=event_date,
        notes=notes,
        is_manual=is_manual
    )
    
    db.add(event)
    
    # Обновляем время последнего использования карты
    card.update_last_used()
    
    db.commit()
    db.refresh(event)
    
    return event


def get_today_events(db: Session, employee_id: int, date: str = None) -> List[AttendanceEvent]:
    """Получает события сотрудника за день"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    return db.query(AttendanceEvent).filter(
        AttendanceEvent.employee_id == employee_id,
        AttendanceEvent.event_date == date
    ).order_by(AttendanceEvent.event_time).all() 