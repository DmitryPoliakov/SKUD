#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import pandas as pd
from datetime import datetime, timedelta
import calendar
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Для работы без GUI
import io
import seaborn as sns

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

# Настройки
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.csv')
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')
TELEGRAM_TOKEN = "7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY"  # Токен пользователя
ALLOWED_USERS = [42291783]  # Список ID пользователей, которым разрешен доступ
ADMIN_USER_ID = 42291783  # ID администратора для уведомлений

# Убедимся, что директория для отчетов существует
os.makedirs(REPORTS_DIR, exist_ok=True)

# Загрузка данных посещаемости
def load_attendance_data():
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE)
    else:
        return pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])

# Генерация отчета за месяц
def generate_monthly_report(year, month):
    df = load_attendance_data()
    
    # Преобразуем даты
    df['date'] = pd.to_datetime(df['date'])
    
    # Фильтруем по году и месяцу
    mask = (df['date'].dt.year == year) & (df['date'].dt.month == month)
    monthly_data = df[mask].copy()
    
    if monthly_data.empty:
        return None, None, None
    
    # Преобразуем время в datetime для расчета разницы
    monthly_data['arrival_time'] = pd.to_datetime(
        monthly_data['date'].dt.strftime('%Y-%m-%d') + ' ' + monthly_data['arrival']
    )
    monthly_data['departure_time'] = pd.to_datetime(
        monthly_data['date'].dt.strftime('%Y-%m-%d') + ' ' + monthly_data['departure']
    )
    
    # Обрабатываем случаи, когда уход на следующий день
    mask = monthly_data['departure_time'] < monthly_data['arrival_time']
    monthly_data.loc[mask, 'departure_time'] = monthly_data.loc[mask, 'departure_time'] + pd.Timedelta(days=1)
    
    # Рассчитываем часы работы
    monthly_data['hours_worked'] = (monthly_data['departure_time'] - monthly_data['arrival_time']).dt.total_seconds() / 3600
    
    # Определяем выходные дни
    monthly_data['is_weekend'] = monthly_data['date'].dt.dayofweek >= 5
    
    # Создаем сводный отчет
    summary = monthly_data.groupby('employee').agg(
        total_days=('date', 'nunique'),
        total_hours=('hours_worked', 'sum'),
        avg_hours=('hours_worked', 'mean')
    ).reset_index()
    
    # Создаем Excel-файл
    month_name = calendar.month_name[month]
    file_name = f"attendance_report_{year}_{month:02d}_{month_name}.xlsx"
    file_path = os.path.join(REPORTS_DIR, file_name)
    
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        # Форматируем и записываем сводный отчет
        summary['avg_hours'] = summary['avg_hours'].round(2)
        summary['total_hours'] = summary['total_hours'].round(2)
        summary.rename(columns={
            'employee': 'Сотрудник',
            'total_days': 'Рабочих дней',
            'total_hours': 'Всего часов',
            'avg_hours': 'Средняя продолжительность дня'
        }, inplace=True)
        summary.to_excel(writer, sheet_name='Сводный отчет', index=False)
        
        # Форматируем и записываем детальный отчет
        detailed = monthly_data[['date', 'employee', 'arrival', 'departure', 'hours_worked', 'is_weekend']].copy()
        detailed.loc[:, 'date'] = detailed['date'].dt.strftime('%Y-%m-%d')
        detailed.loc[:, 'hours_worked'] = detailed['hours_worked'].round(2)
        detailed.rename(columns={
            'date': 'Дата',
            'employee': 'Сотрудник',
            'arrival': 'Приход',
            'departure': 'Уход',
            'hours_worked': 'Часов',
            'is_weekend': 'Выходной'
        }, inplace=True)
        detailed.to_excel(writer, sheet_name='Детальный отчет', index=False)
        
        # Получаем объект workbook и worksheet
        workbook = writer.book
        
        # Форматирование для сводного отчета
        summary_sheet = writer.sheets['Сводный отчет']
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1
        })
        
        for col_num, value in enumerate(summary.columns.values):
            summary_sheet.write(0, col_num, value, header_format)
        
        # Форматирование для детального отчета
        detailed_sheet = writer.sheets['Детальный отчет']
        for col_num, value in enumerate(detailed.columns.values):
            detailed_sheet.write(0, col_num, value, header_format)
        
        # Выделяем выходные дни
        weekend_format = workbook.add_format({'bg_color': '#FFCCCC'})
        for row_num, is_weekend in enumerate(detailed['Выходной']):
            if is_weekend:
                detailed_sheet.set_row(row_num + 1, None, weekend_format)
    
    # Создаем график для визуализации
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    
    # График по сотрудникам
    ax = sns.barplot(x='Сотрудник', y='Всего часов', data=summary)
    plt.title(f'Отработанные часы за {month_name} {year}')
    plt.ylabel('Часы')
    plt.xlabel('Сотрудник')
    plt.tight_layout()
    
    # Сохраняем график
    chart_file = os.path.join(REPORTS_DIR, f"chart_{year}_{month:02d}.png")
    plt.savefig(chart_file)
    plt.close()
    
    return file_path, chart_file, f"{month_name} {year}"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    await update.message.reply_text(
        "Добро пожаловать в бот системы СКУД!\n\n"
        "Доступные команды:\n"
        "• /report - получение отчета за текущий или предыдущий месяц\n"
        "• /add_employee <серийный_номер> <имя> - добавление нового сотрудника"
    )

# Команда для добавления нового сотрудника
async def add_employee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    # Проверяем аргументы команды
    if len(context.args) < 2:
        await update.message.reply_text(
            "Неверный формат команды. Используйте:\n"
            "/add_employee <серийный_номер> <имя_сотрудника>"
        )
        return
    
    serial = context.args[0].upper()  # Преобразуем серийный номер к верхнему регистру
    name = " ".join(context.args[1:])  # Объединяем все оставшиеся аргументы как имя
    
    try:
        # Импортируем модуль main.py для доступа к функции save_new_employee
        import os
        import importlib.util
        
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        spec = importlib.util.spec_from_file_location("main", module_path)
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)
        
        # Добавляем нового сотрудника
        main_module.save_new_employee(serial, name)
        
        await update.message.reply_text(
            f"✅ Сотрудник успешно добавлен!\n\n"
            f"Серийный номер: {serial}\n"
            f"Имя: {name}"
        )
        logger.info(f"Администратор добавил нового сотрудника: {name} с картой {serial}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при добавлении сотрудника: {str(e)}")
        logger.error(f"Ошибка при добавлении сотрудника: {str(e)}")

# Команда /report
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
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
            InlineKeyboardButton(f"Текущий месяц ({calendar.month_name[current_month]})", 
                                callback_data=f"report_{current_year}_{current_month}")
        ],
        [
            InlineKeyboardButton(f"Предыдущий месяц ({calendar.month_name[prev_month]})", 
                                callback_data=f"report_{prev_year}_{prev_month}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Выберите период для отчета:", reply_markup=reply_markup)

# Обработчик нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await query.edit_message_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    # Получаем данные из callback_data
    data = query.data
    
    if data.startswith("report_"):
        # Извлекаем год и месяц
        _, year, month = data.split("_")
        year = int(year)
        month = int(month)
        
        await query.edit_message_text(f"Генерация отчета за {calendar.month_name[month]} {year}...")
        
        # Генерируем отчет
        excel_file, chart_file, period = generate_monthly_report(year, month)
        
        if excel_file is None:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Нет данных за {period}."
            )
            return
        
        # Отправляем Excel-файл
        with open(excel_file, 'rb') as file:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file,
                filename=os.path.basename(excel_file),
                caption=f"Отчет посещаемости за {period}"
            )
        
        # Отправляем график
        with open(chart_file, 'rb') as file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=file,
                caption=f"График отработанных часов за {period}"
            )

# Запуск бота
def main():
    # Проверяем, установлен ли токен
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Пожалуйста, установите токен телеграм-бота в переменной TELEGRAM_TOKEN")
        return
    
    # Создаем приложение
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("add_employee", add_employee))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Запускаем бота
    logger.info("Запуск телеграм-бота СКУД")
    application.run_polling()

# Функция для отправки уведомлений администратору
async def send_admin_notification(message):
    """
    Отправляет уведомление администратору
    
    Args:
        message (str): Текст уведомления
    """
    if not ADMIN_USER_ID:
        logger.warning("ID администратора не указан, уведомление не отправлено")
        return
    
    try:
        # Создаем временный бот для отправки сообщения
        bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build().bot
        await bot.send_message(chat_id=ADMIN_USER_ID, text=message)
        logger.info(f"Уведомление администратору отправлено: {message}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}")

# Синхронная версия для использования из других модулей
def notify_admin(message):
    """
    Синхронная обертка для отправки уведомлений администратору
    
    Args:
        message (str): Текст уведомления
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(send_admin_notification(message))

if __name__ == '__main__':
    main() 