#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import logging
import json
import calendar
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from utils.data_manager import data_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаем экземпляры бота и диспетчера
bot = Bot(token=config.TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class EmployeeStates(StatesGroup):
    waiting_for_employee_data = State()

def check_user_access(user_id: int) -> bool:
    """Проверяет доступ пользователя к боту"""
    # Исключаем сообщения от самого бота
    if user_id == 7853971577:  # ID нашего бота
        return False
        
    if not config.ALLOWED_USERS:  # Если список пуст, разрешаем всем
        return True
    return user_id in config.ALLOWED_USERS

async def send_access_denied(message: types.Message):
    """Отправляет сообщение об отказе в доступе"""
    user_id = message.from_user.id
    
    # НЕ отправляем сообщение об отказе самому боту
    if user_id == 7853971577:
        logger.info(f"🚫 ACCESS_DENIED: Игнорируем отказ доступа для самого бота {user_id}")
        return
        
    await message.reply("У вас нет доступа к этому боту.")
    logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")

async def notify_admin(message_text: str):
    """Отправляет уведомление администратору через новую систему уведомлений"""
    try:
        from utils.notifications import send_notification
        await send_notification(message_text)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Создаем клавиатуру с кнопками команд
    keyboard = [
        [InlineKeyboardButton(text="Отчет по месяцам", callback_data="menu_report")],
        [InlineKeyboardButton(text="Отчеты через Web App", web_app=WebAppInfo(url=config.WEBAPP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.reply(
        "Добро пожаловать в бот системы СКУД!\n\n"
        "🔹 Используйте кнопки меню для быстрого доступа\n\n"
        "Доступные команды:\n"
        "• /report - получение отчета за любой месяц\n"
        "• /check_data - проверка данных в реальном времени\n"
        "• /add_employee - добавление нового сотрудника\n"
        "• /webapp - открыть отчеты через Web App\n"
        "• /diagnose - диагностика проблем с данными",
        reply_markup=reply_markup
    )

@dp.message(Command("diagnose"))
async def cmd_diagnose(message: types.Message):
    """Обработчик команды /diagnose"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    await message.reply("🔍 Запуск диагностики данных...")
    
    # Запускаем диагностику
    report = data_manager.diagnose_data()
    await message.reply(report)

@dp.message(Command("check_data"))
async def cmd_check_data(message: types.Message):
    """Обработчик команды /check_data"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    await message.reply("🔍 Проверка данных в реальном времени...")
    
    # Получаем статистику данных
    stats = data_manager.get_data_statistics()
    
    if stats['total_records'] == 0:
        await message.reply("❌ Данные не найдены")
        return
    
    # Формируем сообщение
    text = "📊 Проверка данных СКУД\n\n"
    text += f"📅 Всего записей: {stats['total_records']}\n"
    text += f"📅 Период: {stats['period']['start']} - {stats['period']['end']}\n"
    text += f"👥 Уникальных сотрудников: {stats['employees_count']}\n\n"
    
    # Добавляем информацию о последних днях
    text += "📈 Последние 5 дней:\n"
    missing_days = 0
    
    for day_info in stats['recent_days']:
        if day_info['has_data']:
            text += f"✅ {day_info['date']}: {day_info['records_count']} записей\n"
        else:
            text += f"❌ {day_info['date']}: нет данных\n"
            missing_days += 1
    
    if missing_days > 0:
        text += f"\n⚠️ Отсутствуют данные за {missing_days} дней из последних 5"
    else:
        text += f"\n✅ Данные за последние 5 дней присутствуют"
    
    await message.reply(text)

@dp.message(Command("report"))
async def cmd_report(message: types.Message):
    """Обработчик команды /report"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Получаем текущую дату
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    # Получаем предыдущий месяц
    prev_month = current_month - 1
    prev_year = current_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    
    # Создаем клавиатуру с кнопками для выбора месяца
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Текущий месяц ({calendar.month_name[current_month]})", 
                callback_data=f"report_{current_year}_{current_month}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Предыдущий месяц ({calendar.month_name[prev_month]})", 
                callback_data=f"report_{prev_year}_{prev_month}"
            )
        ],
        [
            InlineKeyboardButton(
                text="Открыть отчеты через Web App", 
                web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.reply("Выберите период для отчета:", reply_markup=reply_markup)

@dp.message(Command("add_employee"))
async def cmd_add_employee(message: types.Message, state: FSMContext):
    """Обработчик команды /add_employee"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Проверяем аргументы команды
    args = message.text.split()[1:]  # Убираем саму команду
    
    if len(args) < 2:
        await message.reply(
            "Неверный формат команды. Используйте:\n"
            "/add_employee <серийный_номер> <имя_сотрудника>\n\n"
            "Пример: /add_employee ABC123 Иванов Иван"
        )
        return
    
    serial = args[0].upper()  # Преобразуем серийный номер к верхнему регистру
    name = " ".join(args[1:])  # Объединяем все оставшиеся аргументы как имя
    
    # Добавляем нового сотрудника
    if data_manager.add_employee(serial, name):
        await message.reply(
            f"✅ Сотрудник успешно добавлен!\n\n"
            f"Серийный номер: {serial}\n"
            f"Имя: {name}"
        )
        logger.info(f"Пользователь {user_id} добавил нового сотрудника: {name} с картой {serial}")
    else:
        await message.reply(f"❌ Ошибка при добавлении сотрудника")
        logger.error(f"Ошибка при добавлении сотрудника пользователем {user_id}")

@dp.message(Command("webapp"))
async def cmd_webapp(message: types.Message):
    """Обработчик команды /webapp"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Создаем кнопку для открытия Web App
    keyboard = [[InlineKeyboardButton(text="Открыть отчеты", web_app=WebAppInfo(url=config.WEBAPP_URL))]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.reply(
        "Нажмите кнопку для просмотра отчетов в Telegram Web App:",
        reply_markup=reply_markup
    )

@dp.callback_query(F.data.startswith("report_"))
async def handle_report_callback(callback: types.CallbackQuery):
    """Обработчик нажатий на кнопки отчетов"""
    user_id = callback.from_user.id
    
    if not check_user_access(user_id):
        await callback.answer("У вас нет доступа к этому боту.", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем данные из callback_data
    data = callback.data
    
    # Извлекаем год и месяц
    _, year, month = data.split("_")
    year = int(year)
    month = int(month)
    
    logger.info(f"Запрос отчета за {calendar.month_name[month]} {year}")
    await callback.message.edit_text(f"Генерация отчета за {calendar.month_name[month]} {year}...")
    
    # Генерируем отчет
    excel_file, chart_file, period = data_manager.generate_monthly_report(year, month)
    
    if excel_file is None:
        logger.warning(f"Не удалось сгенерировать отчет за {calendar.month_name[month]} {year}")
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=f"Нет данных за {period}."
        )
        return
    
    logger.info(f"Отчет успешно сгенерирован: {excel_file}")
    
    # Загружаем данные для показа сводных цифр
    stats = await get_monthly_summary(year, month)
    
    if stats:
        # Создаем сообщение со сводными цифрами
        summary_message = f"📊 Сводные цифры за {period}:\n\n"
        summary_message += f"🕐 Общее вых: {stats['weekend_hours']:.1f} ч\n"
        summary_message += f"🕐 Общее будни: {stats['weekday_hours']:.1f} ч\n"
        summary_message += f"🕐 Общий итог: {stats['total_hours']:.1f} ч\n\n"
        summary_message += f"📈 Сотрудников: {stats['employees_count']}\n"
        summary_message += f"📅 Рабочих дней: {stats['working_days']}"
        
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=summary_message
        )
    
    # Отправляем Excel-файл
    with open(excel_file, 'rb') as file:
        document = BufferedInputFile(file.read(), filename=f"attendance_report_{period.replace(' ', '_')}.xlsx")
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=document,
            caption=f"📋 Отчет посещаемости за {period}"
        )
    
    # Отправляем график
    with open(chart_file, 'rb') as file:
        photo = BufferedInputFile(file.read(), filename=f"chart_{period.replace(' ', '_')}.png")
        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo,
            caption=f"📊 График отработанных часов за {period}"
        )

@dp.callback_query(F.data == "menu_report")
async def handle_menu_report(callback: types.CallbackQuery):
    """Обработчик кнопки отчета из главного меню"""
    user_id = callback.from_user.id
    
    if not check_user_access(user_id):
        await callback.answer("У вас нет доступа к этому боту.", show_alert=True)
        return
        
    await callback.answer()
    
    # Получаем текущую дату
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    # Получаем предыдущий месяц
    prev_month = current_month - 1
    prev_year = current_year
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    
    # Создаем клавиатуру с кнопками для выбора месяца
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Текущий месяц ({calendar.month_name[current_month]})", 
                callback_data=f"report_{current_year}_{current_month}"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Предыдущий месяц ({calendar.month_name[prev_month]})", 
                callback_data=f"report_{prev_year}_{prev_month}"
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Редактируем исходное сообщение
    await callback.message.edit_text("Выберите период для отчета:", reply_markup=reply_markup)

@dp.callback_query(F.data == "diagnose")
async def handle_diagnose_callback(callback: types.CallbackQuery):
    """Обработчик кнопки диагностики"""
    user_id = callback.from_user.id
    
    if not check_user_access(user_id):
        await callback.answer("У вас нет доступа к этому боту.", show_alert=True)
        return
        
    await callback.answer()
    await cmd_diagnose(callback.message)



# Глобальный middleware для отладки всех updates
@dp.update.outer_middleware()
async def debug_middleware(handler, event, data):
    """Middleware для отладки всех входящих updates"""
    # Проверяем любые типы updates на предмет ID бота
    user_id = None
    
    # Проверяем все возможные типы updates
    if hasattr(event, 'message') and event.message and hasattr(event.message, 'from_user'):
        user_id = event.message.from_user.id
        username = event.message.from_user.username or "без username"
        
        # Специальная обработка WebApp данных
        if hasattr(event.message, 'web_app_data') and event.message.web_app_data:
            logger.info(f"🔍 MIDDLEWARE: WebApp данные от ID: {user_id} (@{username})")
        else:
            text = event.message.text or event.message.caption or "без текста"
            logger.info(f"🔍 MIDDLEWARE: Сообщение от ID: {user_id} (@{username}): '{text}'")
        
    elif hasattr(event, 'callback_query') and event.callback_query and hasattr(event.callback_query, 'from_user'):
        user_id = event.callback_query.from_user.id
        username = event.callback_query.from_user.username or "без username"
        logger.info(f"🔍 MIDDLEWARE: Callback от ID: {user_id} (@{username})")
        
    elif hasattr(event, 'inline_query') and event.inline_query and hasattr(event.inline_query, 'from_user'):
        user_id = event.inline_query.from_user.id
        logger.info(f"🔍 MIDDLEWARE: Inline query от ID: {user_id}")
        
    elif hasattr(event, 'edited_message') and event.edited_message and hasattr(event.edited_message, 'from_user'):
        user_id = event.edited_message.from_user.id
        logger.info(f"🔍 MIDDLEWARE: Edited message от ID: {user_id}")
        
    else:
        logger.info(f"🔍 MIDDLEWARE: Неопознанный тип update: {type(event)}")
        
    # ПОЛНОЕ ИГНОРИРОВАНИЕ любых updates от самого бота
    if user_id == 7853971577:
        logger.info(f"🚫 MIDDLEWARE: ПОЛНОЕ ИГНОРИРОВАНИЕ update от бота {user_id}")
        return None  # Полная остановка обработки
    
    return await handler(event, data)

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    """Обработчик данных от Web App"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    try:
        # Получаем данные от Web App
        raw_data = message.web_app_data.data
        logger.info(f"🔍 RAW данные от Web App: {raw_data}")
        
        data = json.loads(raw_data)
        logger.info(f"📥 Получены данные от Web App: {data}")
        
        action = data.get('action')
        logger.info(f"🎯 Действие: {action}")
        
        if action == 'generate_report':
            year = int(data.get('year'))
            month = int(data.get('month'))
            
            await message.reply(f"Генерация отчета за {calendar.month_name[month]} {year}...")
            
            # Генерируем отчет
            excel_file, chart_file, period = data_manager.generate_monthly_report(year, month)
            
            if excel_file is None:
                await message.reply(f"Нет данных за {period}.")
                return
            
            # Загружаем данные для показа сводных цифр
            stats = await get_monthly_summary(year, month)
            
            if stats:
                # Создаем сообщение со сводными цифрами
                summary_message = f"📊 Сводные цифры за {period}:\n\n"
                summary_message += f"🕐 Общее вых: {stats['weekend_hours']:.1f} ч\n"
                summary_message += f"🕐 Общее будни: {stats['weekday_hours']:.1f} ч\n"
                summary_message += f"🕐 Общий итог: {stats['total_hours']:.1f} ч\n\n"
                summary_message += f"📈 Сотрудников: {stats['employees_count']}\n"
                summary_message += f"📅 Рабочих дней: {stats['working_days']}"
                
                await message.reply(summary_message)
            
            # Отправляем Excel-файл
            with open(excel_file, 'rb') as file:
                document = BufferedInputFile(file.read(), filename=f"attendance_report_{period.replace(' ', '_')}.xlsx")
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=document,
                    caption=f"📋 Отчет посещаемости за {period}"
                )
            
            # Отправляем график
            with open(chart_file, 'rb') as file:
                photo = BufferedInputFile(file.read(), filename=f"chart_{period.replace(' ', '_')}.png")
                await bot.send_photo(
                    chat_id=message.chat.id,
                    photo=photo,
                    caption=f"📊 График отработанных часов за {period}"
                )
        
        elif action == 'view_report':
            report_url = data.get('report_url')
            report_name = data.get('report_name')
            
            logger.info(f"📁 View report request: {report_name}")
            logger.info(f"🔗 Report URL: {report_url}")
            
            # Извлекаем имя файла из URL
            filename = report_name.strip()
            file_path = os.path.join(config.REPORTS_DIR, filename)
            
            logger.info(f"📂 Looking for file: {file_path}")
            logger.info(f"📋 File exists: {os.path.exists(file_path)}")
            
            if os.path.exists(file_path):
                # Отправляем файл пользователю
                logger.info(f"📤 Sending file: {filename}")
                with open(file_path, 'rb') as file:
                    document = BufferedInputFile(file.read(), filename=filename)
                    await bot.send_document(
                        chat_id=message.chat.id,
                        document=document,
                        caption=f"Отчет: {filename}"
                    )
            else:
                # Если файл не найден, отправляем ссылку
                await message.reply(
                    f"Вы выбрали отчет: {report_name}\n"
                    f"Скачать можно по ссылке: {report_url}"
                )
        
        else:
            await message.reply(f"Неизвестное действие: {action}")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке данных от Web App: {str(e)}")
        await message.reply(f"Произошла ошибка при обработке данных: {str(e)}")

# Отладочный обработчик для всех сообщений (должен быть последним)
@dp.message()
async def handle_all_messages(message: types.Message):
    """Отладочный обработчик всех сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    text = message.text or "без текста"
    
    logger.info(f"📩 HANDLER: Получено сообщение от пользователя ID: {user_id} (@{username}): '{text}'")
    
    # Проверяем доступ
    if not check_user_access(user_id):
        logger.warning(f"❌ HANDLER: Попытка доступа от неавторизованного пользователя: {user_id} (@{username})")
        await send_access_denied(message)
        return
    
    logger.info(f"✅ HANDLER: Пользователь {user_id} авторизован, отправляем ответ")
    # Если сообщение не обработано другими хендлерами
    await message.reply("Команда не распознана. Используйте /start для списка команд.")

async def get_monthly_summary(year: int, month: int) -> dict:
    """Получает сводную статистику за месяц"""
    try:
        df = data_manager.load_attendance_data()
        if df.empty:
            return None
        
        import pandas as pd
        
        # Преобразуем даты
        df['date'] = pd.to_datetime(df['date'])
        
        # Фильтруем по году и месяцу
        mask = (df['date'].dt.year == year) & (df['date'].dt.month == month)
        monthly_data = df[mask].copy()
        
        if monthly_data.empty:
            return None
        
        # Рассчитываем часы работы
        monthly_data['arrival_time'] = pd.to_datetime(
            monthly_data['date'].dt.strftime('%Y-%m-%d') + ' ' + monthly_data['arrival']
        )
        monthly_data['departure_time'] = pd.to_datetime(
            monthly_data['date'].dt.strftime('%Y-%m-%d') + ' ' + monthly_data['departure']
        )
        
        # Обрабатываем случаи, когда уход на следующий день
        mask = monthly_data['departure_time'] < monthly_data['arrival_time']
        monthly_data.loc[mask, 'departure_time'] = monthly_data.loc[mask, 'departure_time'] + pd.Timedelta(days=1)
        
        monthly_data['hours_worked'] = (monthly_data['departure_time'] - monthly_data['arrival_time']).dt.total_seconds() / 3600
        monthly_data['is_weekend'] = monthly_data['date'].dt.dayofweek >= 5
        
        # Сводные цифры
        weekend_data = monthly_data[monthly_data['is_weekend'] == True]
        weekday_data = monthly_data[monthly_data['is_weekend'] == False]
        
        weekend_total_hours = weekend_data['hours_worked'].sum() if not weekend_data.empty else 0
        weekday_total_hours = weekday_data['hours_worked'].sum() if not weekday_data.empty else 0
        total_hours = monthly_data['hours_worked'].sum()
        
        return {
            'weekend_hours': weekend_total_hours,
            'weekday_hours': weekday_total_hours,
            'total_hours': total_hours,
            'employees_count': monthly_data['employee'].nunique(),
            'working_days': monthly_data['date'].nunique()
        }
    except Exception as e:
        logger.error(f"Ошибка при получении сводной статистики: {e}")
        return None

async def send_admin_notification(message: str):
    """Отправляет уведомление администратору"""
    if not config.ADMIN_USER_ID:
        logger.warning("ID администратора не указан, уведомление не отправлено")
        return
    
    try:
        await bot.send_message(chat_id=config.ADMIN_USER_ID, text=message)
        logger.info(f"Уведомление администратору отправлено: {message}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")

async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск Telegram бота СКУД на aiogram")
    
    # Краткая проверка доступности данных при старте (без полной диагностики)
    try:
        stats = data_manager.get_data_statistics()
        logger.info(f"Данные СКУД: {stats['total_records']} записей, {stats['employees_count']} сотрудников")
    except Exception as e:
        logger.warning(f"Не удалось проверить данные при старте: {e}")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
