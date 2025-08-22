#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Упрощенная версия СКУД бота на aiogram для тестирования
Без зависимостей от pandas/matplotlib
"""

import asyncio
import logging
import json
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.filters import Command

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

# Конфигурация
TELEGRAM_TOKEN = "8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM"
ALLOWED_USERS = []  # Пустой список = доступ для всех
WEBAPP_URL = "https://example.com"  # Для тестирования WebApp (замените на реальный HTTPS URL)

# Создаем экземпляры бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

def check_user_access(user_id: int) -> bool:
    """Проверяет доступ пользователя к боту"""
    if not ALLOWED_USERS:  # Если список пуст, разрешаем всем
        return True
    return user_id in ALLOWED_USERS

async def send_access_denied(message: types.Message):
    """Отправляет сообщение об отказе в доступе"""
    await message.reply("У вас нет доступа к этому боту.")
    logger.warning(f"Попытка доступа от неавторизованного пользователя: {message.from_user.id}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Создаем клавиатуру с кнопками команд (без WebApp для тестирования)
    keyboard = [
        [InlineKeyboardButton(text="Проверить данные", callback_data="check_data")],
        [InlineKeyboardButton(text="Диагностика", callback_data="diagnose")],
        [InlineKeyboardButton(text="Информация", callback_data="info")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.reply(
        "🤖 Добро пожаловать в СКУД бот на aiogram!\n\n"
        "📱 Тестовая версия для локального тестирования\n\n"
        "Доступные команды:\n"
        "• /start - главное меню\n"
        "• /status - проверка статуса\n"
        "• /info - информация о системе\n"
        "• /webapp - открыть веб-приложение\n\n"
        "Токен: 8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM\n"
        "Для переноса на продакшен смените токен в config.py",
        reply_markup=reply_markup
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Обработчик команды /status"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Проверяем наличие файлов данных
    data_dir = "data"
    attendance_file = os.path.join(data_dir, "attendance.csv")
    employees_file = os.path.join(data_dir, "employees.json")
    
    status_text = "📊 Статус системы СКУД\n\n"
    
    if os.path.exists(data_dir):
        status_text += "✅ Директория данных: найдена\n"
    else:
        status_text += "❌ Директория данных: не найдена\n"
    
    if os.path.exists(attendance_file):
        file_size = os.path.getsize(attendance_file)
        status_text += f"✅ Файл посещаемости: найден ({file_size} байт)\n"
    else:
        status_text += "❌ Файл посещаемости: не найден\n"
    
    if os.path.exists(employees_file):
        status_text += "✅ Файл сотрудников: найден\n"
        try:
            with open(employees_file, 'r', encoding='utf-8') as f:
                employees = json.load(f)
                status_text += f"👥 Количество сотрудников: {len(employees)}\n"
        except:
            status_text += "⚠️ Ошибка чтения файла сотрудников\n"
    else:
        status_text += "❌ Файл сотрудников: не найден\n"
    
    status_text += f"\n🕐 Время проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await message.reply(status_text)

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    """Обработчик команды /info"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    info_text = (
        "ℹ️ Информация о системе\n\n"
        "🤖 Бот: СКУД aiogram версия\n"
        "📱 Библиотека: aiogram 3.13.1\n"
        "🔧 Тестовый токен: 8044045216...\n"
        "🌐 WebApp URL: localhost:5000\n\n"
        "🔄 Возможности:\n"
        "• Проверка статуса системы\n"
        "• Интеграция с WebApp\n"
        "• Обработка callback кнопок\n"
        "• Управление доступом пользователей\n\n"
        "📝 Для полного функционала установите:\n"
        "• pandas (обработка данных)\n"
        "• matplotlib (графики)\n"
        "• xlsxwriter (Excel отчеты)\n\n"
        "🚀 Готов к деплою на Linux сервер!"
    )
    
    await message.reply(info_text)

@dp.message(Command("webapp"))
async def cmd_webapp(message: types.Message):
    """Обработчик команды /webapp"""
    user_id = message.from_user.id
    
    if not check_user_access(user_id):
        await send_access_denied(message)
        return
    
    # Создаем кнопку для открытия Web App
    keyboard = [[InlineKeyboardButton(text="🌐 Открыть отчеты", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.reply(
        "🌐 Telegram Web App\n\n"
        "Нажмите кнопку для открытия веб-интерфейса отчетов.\n"
        "В тестовом режиме WebApp будет пытаться подключиться к localhost:5000",
        reply_markup=reply_markup
    )

@dp.callback_query(F.data == "check_data")
async def handle_check_data(callback: types.CallbackQuery):
    """Обработчик кнопки проверки данных"""
    await callback.answer()
    
    # Простая проверка без pandas
    data_dir = "data"
    attendance_file = os.path.join(data_dir, "attendance.csv")
    
    if os.path.exists(attendance_file):
        try:
            with open(attendance_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                records_count = len(lines) - 1  # Минус заголовок
            
            response = (
                f"📊 Проверка данных\n\n"
                f"✅ Файл найден: {attendance_file}\n"
                f"📝 Записей в файле: {records_count}\n"
                f"🕐 Проверено: {datetime.now().strftime('%H:%M:%S')}"
            )
        except Exception as e:
            response = f"❌ Ошибка чтения файла: {str(e)}"
    else:
        response = "❌ Файл данных не найден"
    
    await bot.send_message(callback.message.chat.id, response)

@dp.callback_query(F.data == "diagnose")
async def handle_diagnose(callback: types.CallbackQuery):
    """Обработчик кнопки диагностики"""
    await callback.answer()
    
    report = "🔍 Диагностика системы\n\n"
    
    # Проверяем структуру проекта
    files_to_check = [
        ("config.py", "Конфигурация"),
        ("bot.py", "Основной бот"),
        ("utils/data_manager.py", "Менеджер данных"),
        ("data/employees.json", "Список сотрудников"),
        ("data/attendance.csv", "Данные посещаемости"),
        ("requirements.txt", "Зависимости"),
        ("README.md", "Документация")
    ]
    
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            report += f"✅ {description}: найден\n"
        else:
            report += f"❌ {description}: не найден\n"
    
    # Проверяем директории
    dirs_to_check = [
        ("data", "Данные"),
        ("data/reports", "Отчеты"),
        ("utils", "Утилиты")
    ]
    
    report += "\n📁 Директории:\n"
    for dir_path, description in dirs_to_check:
        if os.path.exists(dir_path):
            report += f"✅ {description}: найдена\n"
        else:
            report += f"❌ {description}: не найдена\n"
    
    report += f"\n🕐 Диагностика завершена: {datetime.now().strftime('%H:%M:%S')}"
    
    await bot.send_message(callback.message.chat.id, report)

@dp.callback_query(F.data == "info")
async def handle_info(callback: types.CallbackQuery):
    """Обработчик кнопки информации"""
    await callback.answer()
    
    info_text = (
        "Информация о системе\n\n"
        "Бот: СКУД aiogram версия\n"
        "Библиотека: aiogram 3.13.1\n"
        "Тестовый токен: 8044045216...\n"
        "WebApp URL: example.com\n\n"
        "Возможности:\n"
        "• Проверка статуса системы\n"
        "• Интеграция с WebApp\n"
        "• Обработка callback кнопок\n"
        "• Управление доступом пользователей\n\n"
        "Для полного функционала установите:\n"
        "• pandas (обработка данных)\n"
        "• matplotlib (графики)\n"
        "• xlsxwriter (Excel отчеты)\n\n"
        "Готов к деплою на Linux сервер!"
    )
    
    await bot.send_message(callback.message.chat.id, info_text)

async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск СКУД бота на aiogram (тестовая версия)")
    logger.info(f"Токен: {TELEGRAM_TOKEN}")
    logger.info(f"WebApp URL: {WEBAPP_URL}")
    
    try:
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        logger.info("Бот остановлен")

if __name__ == '__main__':
    asyncio.run(main())
