#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram бот для системы СКУД Enhanced на Aiogram 3.x
"""

import asyncio
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, List

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, InputFile, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.orm import Session

from .config import config
from .database import get_db, db_manager
from .models import (
    Employee, RFIDCard, AttendanceEvent, RegistrationRequest,
    UserRole, EventType, get_card_by_serial, create_attendance_event
)
from .services.reports import ReportService
from .services.registration import RegistrationService
from .services.notifications import NotificationService


class RegistrationStates(StatesGroup):
    """Состояния для регистрации сотрудника"""
    waiting_for_name = State()
    waiting_for_confirmation = State()


class AddEmployeeStates(StatesGroup):
    """Состояния для добавления сотрудника администратором"""
    waiting_for_card_serial = State()
    waiting_for_name = State()
    waiting_for_telegram_id = State()


# Инициализация бота
bot = Bot(
    token=config.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Создаем диспетчер и роутер
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Сервисы
report_service = ReportService()
registration_service = RegistrationService()
notification_service = NotificationService(bot)


def get_user_role(telegram_id: str, db: Session) -> UserRole:
    """Определяет роль пользователя"""
    employee = db.query(Employee).filter(Employee.telegram_id == telegram_id).first()
    if employee:
        return employee.role
    return UserRole.EMPLOYEE


def is_admin(telegram_id: str, db: Session) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return get_user_role(telegram_id, db) == UserRole.ADMIN


def create_main_menu(is_admin_user: bool = False) -> InlineKeyboardMarkup:
    """Создает главное меню"""
    builder = InlineKeyboardBuilder()
    
    # Отчеты
    builder.row(
        InlineKeyboardButton(
            text="📊 Отчеты", 
            callback_data="menu_reports"
        )
    )
    
    # Веб-приложение
    if config.WEBAPP_URL:
        builder.row(
            InlineKeyboardButton(
                text="🌐 Web App", 
                web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        )
    
    # Настройки уведомлений
    builder.row(
        InlineKeyboardButton(
            text="🔔 Настройки", 
            callback_data="menu_settings"
        )
    )
    
    if is_admin_user:
        # Административные функции
        builder.row(
            InlineKeyboardButton(
                text="👥 Сотрудники", 
                callback_data="menu_employees"
            ),
            InlineKeyboardButton(
                text="💳 Карты", 
                callback_data="menu_cards"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text="📈 Статистика", 
                callback_data="menu_stats"
            ),
            InlineKeyboardButton(
                text="⚙️ Система", 
                callback_data="menu_system"
            )
        )
    
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    telegram_id = str(message.from_user.id)
    
    with next(get_db()) as db:
        employee = db.query(Employee).filter(Employee.telegram_id == telegram_id).first()
        is_admin_user = employee and employee.is_admin if employee else False
        
        if not employee:
            # Пользователь не зарегистрирован
            await message.answer(
                "👋 Добро пожаловать в систему СКУД Enhanced!\n\n"
                "🔍 Вы не зарегистрированы в системе. Обратитесь к администратору "
                "для получения ссылки на регистрацию или добавления в систему.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="📞 Связаться с админом",
                        callback_data="contact_admin"
                    )
                ]])
            )
            return
        
        # Пользователь зарегистрирован
        welcome_text = f"👋 Добро пожаловать, <b>{employee.name}</b>!\n\n"
        
        if is_admin_user:
            welcome_text += "🔧 Вы являетесь администратором системы.\n"
        
        welcome_text += (
            "📋 Доступные функции:\n"
            "• 📊 Просмотр отчетов посещаемости\n"
            "• 🔔 Настройка уведомлений\n"
            "• 🌐 Веб-интерфейс системы\n"
        )
        
        if is_admin_user:
            welcome_text += (
                "\n🔧 Административные функции:\n"
                "• 👥 Управление сотрудниками\n"
                "• 💳 Управление картами\n"
                "• 📈 Системная статистика\n"
            )
        
        await message.answer(
            welcome_text,
            reply_markup=create_main_menu(is_admin_user)
        )


@router.message(Command("add_employee"))
async def cmd_add_employee(message: Message, state: FSMContext):
    """Команда для добавления сотрудника (только для админов)"""
    telegram_id = str(message.from_user.id)
    
    with next(get_db()) as db:
        if not is_admin(telegram_id, db):
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            return
        
        args = message.text.split()[1:]  # Убираем /add_employee
        
        if len(args) >= 2:
            # Формат: /add_employee SERIAL_NUMBER Name
            serial = args[0].upper()
            name = " ".join(args[1:])
            
            await add_employee_with_card(message, db, serial, name)
        else:
            # Интерактивное добавление
            await message.answer(
                "👥 Добавление нового сотрудника\n\n"
                "Введите серийный номер карты:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation")
                ]])
            )
            await state.set_state(AddEmployeeStates.waiting_for_card_serial)


async def add_employee_with_card(message: Message, db: Session, serial: str, name: str, telegram_id: str = None):
    """Добавляет сотрудника с картой"""
    try:
        # Проверяем, существует ли карта
        existing_card = get_card_by_serial(db, serial)
        if existing_card:
            await message.answer(
                f"❌ Карта {serial} уже зарегистрирована на сотрудника: "
                f"{existing_card.employee.name if existing_card.employee else 'Неизвестно'}"
            )
            return
        
        # Создаем сотрудника
        employee = Employee(
            name=name,
            telegram_id=telegram_id,
            role=UserRole.EMPLOYEE,
            notifications_enabled=True,
            arrival_notifications=True,
            departure_notifications=True
        )
        db.add(employee)
        db.flush()
        
        # Создаем карту
        card = RFIDCard(
            serial_number=serial,
            employee_id=employee.id,
            card_type="MIFARE",
            description=f"Карта для {name}"
        )
        db.add(card)
        db.commit()
        
        success_text = f"✅ Сотрудник успешно добавлен!\n\n"
        success_text += f"👤 Имя: <b>{name}</b>\n"
        success_text += f"💳 Карта: <code>{serial}</code>\n"
        
        if telegram_id:
            success_text += f"📱 Telegram ID: <code>{telegram_id}</code>\n"
        
        await message.answer(success_text)
        logger.info(f"Администратор добавил сотрудника: {name} с картой {serial}")
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении сотрудника: {e}")
        await message.answer(f"❌ Ошибка при добавлении сотрудника: {e}")


@router.message(Command("report"))
async def cmd_report(message: Message):
    """Команда для получения отчета"""
    await show_reports_menu(message)


@router.callback_query(F.data == "menu_reports")
async def show_reports_menu(message_or_query):
    """Показывает меню отчетов"""
    # Определяем, что пришло - сообщение или callback
    if isinstance(message_or_query, CallbackQuery):
        query = message_or_query
        message = query.message
        await query.answer()
    else:
        message = message_or_query
        query = None
    
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    # Предыдущий месяц
    prev_month = current_month - 1
    prev_year = current_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    
    builder = InlineKeyboardBuilder()
    
    # Кнопки для отчетов
    builder.row(
        InlineKeyboardButton(
            text=f"📊 Текущий месяц ({now.strftime('%B')})",
            callback_data=f"report_{current_year}_{current_month}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=f"📊 Предыдущий месяц",
            callback_data=f"report_{prev_year}_{prev_month}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="📈 Статистика за неделю",
            callback_data="report_week"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )
    )
    
    text = "📊 <b>Отчеты посещаемости</b>\n\nВыберите период:"
    
    if query:
        await message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("report_"))
async def handle_report_request(query: CallbackQuery):
    """Обрабатывает запрос на генерацию отчета"""
    await query.answer()
    
    data_parts = query.data.split("_")
    
    if len(data_parts) == 3 and data_parts[0] == "report":
        year = int(data_parts[1])
        month = int(data_parts[2])
        
        await query.message.edit_text(
            f"📊 Генерирую отчет за {month:02d}.{year}...\n"
            "⏳ Пожалуйста, подождите..."
        )
        
        try:
            with next(get_db()) as db:
                # Генерируем отчет
                excel_file, chart_file, period_name = await report_service.generate_monthly_report(
                    db, year, month
                )
                
                if not excel_file:
                    await query.message.edit_text(
                        f"📊 Нет данных за {period_name}"
                    )
                    return
                
                # Отправляем Excel файл
                document = FSInputFile(excel_file)
                await query.message.answer_document(
                    document=document,
                    caption=f"📊 <b>Отчет посещаемости за {period_name}</b>"
                )
                
                # Отправляем график, если есть
                if chart_file:
                    photo = FSInputFile(chart_file)
                    await query.message.answer_photo(
                        photo=photo,
                        caption=f"📈 <b>График отработанных часов за {period_name}</b>"
                    )
                
                await query.message.edit_text(
                    f"✅ Отчет за {period_name} готов!"
                )
                
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            await query.message.edit_text(
                f"❌ Ошибка при генерации отчета: {e}"
            )
    
    elif data_parts[1] == "week":
        # Недельный отчет
        await query.message.edit_text("📈 Недельные отчеты пока в разработке...")


@router.callback_query(F.data == "menu_settings")
async def show_settings_menu(query: CallbackQuery):
    """Показывает меню настроек"""
    await query.answer()
    telegram_id = str(query.from_user.id)
    
    with next(get_db()) as db:
        employee = db.query(Employee).filter(Employee.telegram_id == telegram_id).first()
        
        if not employee:
            await query.message.edit_text("❌ Вы не зарегистрированы в системе.")
            return
        
        builder = InlineKeyboardBuilder()
        
        # Настройки уведомлений
        notifications_text = "🔔" if employee.notifications_enabled else "🔕"
        builder.row(
            InlineKeyboardButton(
                text=f"{notifications_text} Уведомления: {'ВКЛ' if employee.notifications_enabled else 'ВЫКЛ'}",
                callback_data="toggle_notifications"
            )
        )
        
        if employee.notifications_enabled:
            arrival_text = "🟢" if employee.arrival_notifications else "🔴"
            departure_text = "🟢" if employee.departure_notifications else "🔴"
            
            builder.row(
                InlineKeyboardButton(
                    text=f"{arrival_text} Приход",
                    callback_data="toggle_arrival_notifications"
                ),
                InlineKeyboardButton(
                    text=f"{departure_text} Уход",
                    callback_data="toggle_departure_notifications"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text="🏠 Главное меню",
                callback_data="main_menu"
            )
        )
        
        settings_text = f"⚙️ <b>Настройки для {employee.name}</b>\n\n"
        settings_text += f"📱 Telegram ID: <code>{employee.telegram_id}</code>\n"
        settings_text += f"👤 Роль: {employee.role.value}\n\n"
        settings_text += "Настройте параметры уведомлений:"
        
        await query.message.edit_text(
            settings_text,
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("toggle_"))
async def handle_settings_toggle(query: CallbackQuery):
    """Обрабатывает переключение настроек"""
    await query.answer()
    telegram_id = str(query.from_user.id)
    
    with next(get_db()) as db:
        employee = db.query(Employee).filter(Employee.telegram_id == telegram_id).first()
        
        if not employee:
            await query.message.edit_text("❌ Вы не зарегистрированы в системе.")
            return
        
        setting = query.data.replace("toggle_", "")
        
        if setting == "notifications":
            employee.notifications_enabled = not employee.notifications_enabled
            status = "включены" if employee.notifications_enabled else "отключены"
            await query.answer(f"Уведомления {status}", show_alert=True)
            
        elif setting == "arrival_notifications":
            employee.arrival_notifications = not employee.arrival_notifications
            status = "включены" if employee.arrival_notifications else "отключены"
            await query.answer(f"Уведомления о приходе {status}", show_alert=True)
            
        elif setting == "departure_notifications":
            employee.departure_notifications = not employee.departure_notifications
            status = "включены" if employee.departure_notifications else "отключены"
            await query.answer(f"Уведомления об уходе {status}", show_alert=True)
        
        db.commit()
        
        # Обновляем меню настроек
        await show_settings_menu(query)


@router.callback_query(F.data == "main_menu")
async def show_main_menu(query: CallbackQuery):
    """Возвращает в главное меню"""
    await query.answer()
    telegram_id = str(query.from_user.id)
    
    with next(get_db()) as db:
        is_admin_user = is_admin(telegram_id, db)
        
        await query.message.edit_text(
            "🏠 <b>Главное меню</b>\n\nВыберите действие:",
            reply_markup=create_main_menu(is_admin_user)
        )


# Обработчики для неизвестных карт и регистрации
@router.callback_query(F.data.startswith("handle_unknown_"))
async def handle_unknown_card(query: CallbackQuery):
    """Обрабатывает неизвестную карту"""
    await query.answer()
    
    parts = query.data.split("_")
    if len(parts) != 3:
        return
    
    action = parts[2]  # manual или link
    
    # Получаем серийный номер из текста сообщения
    message_text = query.message.text
    lines = message_text.split('\n')
    serial = None
    
    for line in lines:
        if 'Серийный номер:' in line:
            serial = line.split(':')[1].strip()
            break
    
    if not serial:
        await query.message.edit_text("❌ Не удалось определить серийный номер карты")
        return
    
    if action == "manual":
        # Ручное добавление
        await query.message.edit_text(
            f"👥 Ручное добавление сотрудника\n"
            f"💳 Карта: <code>{serial}</code>\n\n"
            f"Введите имя сотрудника:"
        )
        # Здесь должна быть логика для ожидания ввода имени
        
    elif action == "link":
        # Генерация ссылки
        with next(get_db()) as db:
            try:
                registration_url = await registration_service.create_registration_link(
                    db, serial
                )
                
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(
                        text="📱 Отправить ссылку сотруднику",
                        url=registration_url
                    )
                )
                
                await query.message.edit_text(
                    f"🔗 <b>Ссылка для регистрации создана</b>\n\n"
                    f"💳 Карта: <code>{serial}</code>\n"
                    f"⏰ Действительна до: {(datetime.now() + timedelta(hours=config.REGISTRATION_LINK_EXPIRE_HOURS)).strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"📤 Отправьте эту ссылку сотруднику для самостоятельной регистрации:\n"
                    f"<code>{registration_url}</code>",
                    reply_markup=builder.as_markup()
                )
                
            except Exception as e:
                logger.error(f"Ошибка при создании ссылки регистрации: {e}")
                await query.message.edit_text(f"❌ Ошибка при создании ссылки: {e}")


# Функции для отправки уведомлений
async def send_attendance_notification(employee: Employee, event: AttendanceEvent, card: RFIDCard):
    """Отправляет уведомление о посещаемости"""
    if not employee.telegram_id:
        return
    
    event_emoji = "🟢" if event.event_type == EventType.ARRIVAL else "🔴"
    event_text = "Приход на работу" if event.event_type == EventType.ARRIVAL else "Уход с работы"
    
    local_time = event.local_time
    time_str = local_time.strftime('%H:%M')
    date_str = local_time.strftime('%d.%m.%Y')
    
    message_text = f"{event_emoji} <b>{event_text}</b>\n\n"
    message_text += f"⏰ Время: {time_str}\n"
    message_text += f"📅 Дата: {date_str}\n"
    message_text += f"💳 Карта: <code>{card.serial_number}</code>"
    
    try:
        await bot.send_message(
            chat_id=employee.telegram_id,
            text=message_text
        )
        logger.info(f"Отправлено уведомление сотруднику {employee.name} ({employee.telegram_id})")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления сотруднику {employee.name}: {e}")


async def send_admin_notification(message_text: str):
    """Отправляет уведомление администратору"""
    if not config.TELEGRAM_ADMIN_ID:
        return
    
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_ADMIN_ID,
            text=message_text
        )
        logger.info("Отправлено уведомление администратору")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


async def send_unknown_card_notification(serial: str, timestamp: datetime):
    """Отправляет уведомление о неизвестной карте"""
    if not config.TELEGRAM_ADMIN_ID:
        return
    
    local_time = timestamp.strftime('%d.%m.%Y %H:%M:%S')
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="👤 Добавить вручную",
            callback_data=f"handle_unknown_manual_{serial}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔗 Создать ссылку",
            callback_data=f"handle_unknown_link_{serial}"
        )
    )
    
    message_text = f"🔴 <b>Обнаружена неизвестная карта</b>\n\n"
    message_text += f"💳 Серийный номер: <code>{serial}</code>\n"
    message_text += f"⏰ Время: {local_time}\n\n"
    message_text += f"Выберите действие:"
    
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_ADMIN_ID,
            text=message_text,
            reply_markup=builder.as_markup()
        )
        logger.info(f"Отправлено уведомление о неизвестной карте: {serial}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления о неизвестной карте: {e}")


async def start_bot():
    """Запускает бота"""
    try:
        # Проверяем конфигурацию
        if not config.validate():
            raise Exception("Ошибка конфигурации бота")
        
        logger.info("Запуск Telegram бота СКУД Enhanced...")
        
        # Удаляем вебхук если есть
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"Бот запущен: @{bot_info.username} ({bot_info.full_name})")
        
        # Уведомляем администратора о запуске
        if config.TELEGRAM_ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=config.TELEGRAM_ADMIN_ID,
                    text="🤖 <b>Система СКУД Enhanced запущена</b>\n\n"
                         f"✅ Бот активен: @{bot_info.username}\n"
                         f"🕐 Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление о запуске: {e}")
        
        # Запускаем polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise


async def stop_bot():
    """Останавливает бота"""
    try:
        logger.info("Остановка Telegram бота...")
        
        # Уведомляем администратора об остановке
        if config.TELEGRAM_ADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=config.TELEGRAM_ADMIN_ID,
                    text="🤖 <b>Система СКУД Enhanced остановлена</b>\n\n"
                         f"⏹️ Бот остановлен\n"
                         f"🕐 Время остановки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление об остановке: {e}")
        
        await bot.session.close()
        
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}")


# Экспорт функций для использования в других модулях
__all__ = [
    'bot', 'dp', 'router', 'start_bot', 'stop_bot',
    'send_attendance_notification', 'send_admin_notification', 'send_unknown_card_notification'
]


if __name__ == "__main__":
    # Запуск бота в standalone режиме
    asyncio.run(start_bot()) 