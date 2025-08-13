#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
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

# Альтернативный путь (если запускается из корневой директории проекта)
ALTERNATIVE_DATA_DIR = os.path.join(os.getcwd(), 'data')
ALTERNATIVE_ATTENDANCE_FILE = os.path.join(ALTERNATIVE_DATA_DIR, 'attendance.csv')

# Добавляем отладочную информацию о путях
logger.info(f"Текущая директория: {os.getcwd()}")
logger.info(f"Директория скрипта: {os.path.dirname(os.path.abspath(__file__))}")
logger.info(f"Директория данных: {DATA_DIR}")
logger.info(f"Файл посещаемости: {ATTENDANCE_FILE}")
logger.info(f"Альтернативный файл: {ALTERNATIVE_ATTENDANCE_FILE}")
logger.info(f"Директория отчетов: {REPORTS_DIR}")
logger.info(f"Основной файл существует: {os.path.exists(ATTENDANCE_FILE)}")
logger.info(f"Альтернативный файл существует: {os.path.exists(ALTERNATIVE_ATTENDANCE_FILE)}")

TELEGRAM_TOKEN = "7853971577:AAGjaqm1yeEpy1mY8sk7ll7bnDyS2_cLDGY"  # Токен пользователя
ALLOWED_USERS = [42291783]  # Список ID пользователей, которым разрешен доступ
ADMIN_USER_ID = 42291783  # ID администратора для уведомлений

# URL веб-приложения
WEBAPP_URL = "https://skud-ek.ru/telegram-reports?tgWebApp=1"

# Убедимся, что директория для отчетов существует
os.makedirs(REPORTS_DIR, exist_ok=True)

# Загрузка данных посещаемости
def load_attendance_data():
    """
    Загружает данные посещаемости, используя ту же логику, что и main.py
    """
    logger.info(f"Загрузка данных из файла: {ATTENDANCE_FILE}")
    
    # Сначала пробуем основной путь
    if os.path.exists(ATTENDANCE_FILE):
        df = pd.read_csv(ATTENDANCE_FILE)
        logger.info(f"Файл найден по основному пути, загружено {len(df)} записей")
        if not df.empty:
            logger.info(f"Период данных в файле: с {df['date'].min()} по {df['date'].max()}")
            # Показываем последние 5 записей для диагностики
            logger.info(f"Последние 5 записей:")
            for i, row in df.tail(5).iterrows():
                logger.info(f"  {row['date']} - {row['employee']} - {row['arrival']} - {row['departure']}")
        return df
    
    # Если основной путь не работает, пробуем альтернативный
    logger.info(f"Основной файл не найден, пробуем альтернативный: {ALTERNATIVE_ATTENDANCE_FILE}")
    if os.path.exists(ALTERNATIVE_ATTENDANCE_FILE):
        df = pd.read_csv(ALTERNATIVE_ATTENDANCE_FILE)
        logger.info(f"Файл найден по альтернативному пути, загружено {len(df)} записей")
        if not df.empty:
            logger.info(f"Период данных в файле: с {df['date'].min()} по {df['date'].max()}")
            # Показываем последние 5 записей для диагностики
            logger.info(f"Последние 5 записей:")
            for i, row in df.tail(5).iterrows():
                logger.info(f"  {row['date']} - {row['employee']} - {row['arrival']} - {row['departure']}")
        return df
    
    # Если файл не найден ни по одному пути, создаем пустой DataFrame
    logger.warning(f"Файл данных не найден ни по одному из путей")
    logger.warning(f"Проверенные пути: {ATTENDANCE_FILE}, {ALTERNATIVE_ATTENDANCE_FILE}")
    df = pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])
    df.to_csv(ATTENDANCE_FILE, index=False)
    return df

# Генерация отчета за месяц
def generate_monthly_report(year, month):
    df = load_attendance_data()
    
    # Добавляем отладочную информацию
    logger.info(f"Загружено всего записей: {len(df)}")
    if not df.empty:
        logger.info(f"Период данных: с {df['date'].min()} по {df['date'].max()}")
        
        # Показываем все уникальные даты в данных
        unique_dates = sorted(df['date'].unique())
        logger.info(f"Уникальные даты в данных: {[d.strftime('%Y-%m-%d') for d in unique_dates]}")
    
    # Преобразуем даты
    df['date'] = pd.to_datetime(df['date'])
    
    # Фильтруем по году и месяцу
    mask = (df['date'].dt.year == year) & (df['date'].dt.month == month)
    monthly_data = df[mask].copy()
    
    logger.info(f"Найдено записей за {calendar.month_name[month]} {year}: {len(monthly_data)}")
    
    if monthly_data.empty:
        logger.warning(f"Нет данных за {calendar.month_name[month]} {year}")
        return None, None, None
    
    # Показываем диапазон дат в отфильтрованных данных
    if not monthly_data.empty:
        min_date = monthly_data['date'].min()
        max_date = monthly_data['date'].max()
        logger.info(f"Период данных в отчете: с {min_date.strftime('%Y-%m-%d')} по {max_date.strftime('%Y-%m-%d')}")
        
        # Показываем все уникальные даты в отфильтрованных данных
        unique_filtered_dates = sorted(monthly_data['date'].unique())
        logger.info(f"Даты в отфильтрованных данных: {[d.strftime('%Y-%m-%d') for d in unique_filtered_dates]}")
        
        # Проверяем, есть ли данные за последние дни июля
        july_dates = [d for d in unique_filtered_dates if d.month == 7 and d.day >= 22]
        if july_dates:
            logger.info(f"Найдены данные за последние дни июля: {[d.strftime('%Y-%m-%d') for d in july_dates]}")
        else:
            logger.warning(f"НЕТ данных за последние дни июля (22-31)")
    
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
    
    # Создаем сводный отчет по сотрудникам
    summary = monthly_data.groupby('employee').agg(
        total_days=('date', 'nunique'),
        total_hours=('hours_worked', 'sum'),
        avg_hours=('hours_worked', 'mean')
    ).reset_index()
    
    # Создаем сводные цифры по будням и выходным
    weekend_data = monthly_data[monthly_data['is_weekend'] == True]
    weekday_data = monthly_data[monthly_data['is_weekend'] == False]
    
    weekend_total_hours = weekend_data['hours_worked'].sum() if not weekend_data.empty else 0
    weekday_total_hours = weekday_data['hours_worked'].sum() if not weekday_data.empty else 0
    total_hours = monthly_data['hours_worked'].sum()
    
    logger.info(f"Сотрудников в отчете: {len(summary)}")
    logger.info(f"Часов в выходные: {weekend_total_hours:.2f}")
    logger.info(f"Часов в будни: {weekday_total_hours:.2f}")
    logger.info(f"Общий итог: {total_hours:.2f}")
    
    # Создаем Excel-файл
    month_name = calendar.month_name[month]
    file_name = f"attendance_report_{year}_{month:02d}_{month_name}.xlsx"
    file_path = os.path.join(REPORTS_DIR, file_name)
    
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        # Получаем объект workbook
        workbook = writer.book
        
        # Форматы для заголовков
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'center'
        })
        
        # Формат для чисел
        number_format = workbook.add_format({
            'num_format': '0.0',
            'border': 1
        })
        
        # Формат для выходных дней
        weekend_format = workbook.add_format({
            'bg_color': '#FFCCCC',
            'border': 1
        })
        
        # 1. Сводный отчет по сотрудникам
        summary['avg_hours'] = summary['avg_hours'].round(2)
        summary['total_hours'] = summary['total_hours'].round(2)
        summary.rename(columns={
            'employee': 'Сотрудник',
            'total_days': 'Рабочих дней',
            'total_hours': 'Всего часов',
            'avg_hours': 'Средняя продолжительность дня'
        }, inplace=True)
        summary.to_excel(writer, sheet_name='Сводный отчет', index=False)
        
        # Форматируем сводный отчет
        summary_sheet = writer.sheets['Сводный отчет']
        for col_num, value in enumerate(summary.columns.values):
            summary_sheet.write(0, col_num, value, header_format)
            summary_sheet.set_column(col_num, col_num, 20)
        
        # 2. Детальный отчет с разбивкой по дням
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
        
        # Форматируем детальный отчет
        detailed_sheet = writer.sheets['Детальный отчет']
        for col_num, value in enumerate(detailed.columns.values):
            detailed_sheet.write(0, col_num, value, header_format)
            detailed_sheet.set_column(col_num, col_num, 15)
        
        # Выделяем выходные дни
        for row_num, is_weekend in enumerate(detailed['Выходной']):
            if is_weekend:
                detailed_sheet.set_row(row_num + 1, None, weekend_format)
        
        # 3. Сводные цифры по будням и выходным
        summary_data = pd.DataFrame({
            'Показатель': ['Общее вых', 'Общее будни', 'Общий итог'],
            'Часов': [weekend_total_hours, weekday_total_hours, total_hours]
        })
        summary_data['Часов'] = summary_data['Часов'].round(2)
        summary_data.to_excel(writer, sheet_name='Сводные цифры', index=False)
        
        # Форматируем сводные цифры
        summary_sheet = writer.sheets['Сводные цифры']
        for col_num, value in enumerate(summary_data.columns.values):
            summary_sheet.write(0, col_num, value, header_format)
            summary_sheet.set_column(col_num, col_num, 20)
        
        # Применяем формат для колонки с часами
        summary_sheet.set_column(1, 1, 15, number_format)
    
    # Создаем график для визуализации
    plt.figure(figsize=(12, 8))
    sns.set_style("whitegrid")
    
    # Создаем подграфики
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # График 1: Отработанные часы по сотрудникам
    sns.barplot(x='Сотрудник', y='Всего часов', data=summary, ax=ax1)
    ax1.set_title(f'Отработанные часы за {month_name} {year}')
    ax1.set_ylabel('Часы')
    ax1.set_xlabel('Сотрудник')
    ax1.tick_params(axis='x', rotation=45)
    
    # График 2: Сводные цифры по будням и выходным
    categories = ['Выходные', 'Будни', 'Общий итог']
    values = [weekend_total_hours, weekday_total_hours, total_hours]
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1']
    
    bars = ax2.bar(categories, values, color=colors)
    ax2.set_title(f'Сводные цифры за {month_name} {year}')
    ax2.set_ylabel('Часы')
    
    # Добавляем значения на столбцы
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{value:.1f}', ha='center', va='bottom')
    
    plt.tight_layout()
    
    # Сохраняем график
    chart_file = os.path.join(REPORTS_DIR, f"chart_{year}_{month:02d}.png")
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    logger.info(f"Отчет сгенерирован: {file_path}")
    return file_path, chart_file, f"{month_name} {year}"

# Функция для диагностики состояния данных
def diagnose_data_issue():
    """
    Диагностирует проблемы с данными и выводит подробную информацию
    """
    logger.info("=== ДИАГНОСТИКА ДАННЫХ ===")
    
    # Проверяем пути
    logger.info(f"Текущая директория: {os.getcwd()}")
    logger.info(f"Директория данных: {DATA_DIR}")
    logger.info(f"Файл посещаемости: {ATTENDANCE_FILE}")
    
    # Проверяем существование файлов
    if os.path.exists(ATTENDANCE_FILE):
        logger.info(f"✅ Основной файл данных найден")
        file_size = os.path.getsize(ATTENDANCE_FILE)
        logger.info(f"Размер файла: {file_size} байт")
        
        # Читаем данные
        df = pd.read_csv(ATTENDANCE_FILE)
        logger.info(f"Загружено записей: {len(df)}")
        
        if not df.empty:
            logger.info(f"Период данных: с {df['date'].min()} по {df['date'].max()}")
            
            # Проверяем последние записи
            df['date'] = pd.to_datetime(df['date'])
            latest_date = df['date'].max()
            current_date = datetime.now()
            
            logger.info(f"Последняя запись: {latest_date.strftime('%Y-%m-%d')}")
            logger.info(f"Текущая дата: {current_date.strftime('%Y-%m-%d')}")
            
            # Проверяем, есть ли записи за последние 5 дней
            for i in range(5):
                check_date = current_date - timedelta(days=i)
                check_date_str = check_date.strftime('%Y-%m-%d')
                records_for_date = df[df['date'] == check_date_str]
                
                if not records_for_date.empty:
                    logger.info(f"✅ {check_date_str}: {len(records_for_date)} записей")
                else:
                    logger.warning(f"❌ {check_date_str}: нет записей")
        else:
            logger.warning("Файл данных пуст")
    elif os.path.exists(ALTERNATIVE_ATTENDANCE_FILE):
        logger.info(f"✅ Альтернативный файл данных найден")
        file_size = os.path.getsize(ALTERNATIVE_ATTENDANCE_FILE)
        logger.info(f"Размер файла: {file_size} байт")
        
        # Читаем данные из альтернативного файла
        df = pd.read_csv(ALTERNATIVE_ATTENDANCE_FILE)
        logger.info(f"Загружено записей: {len(df)}")
        
        if not df.empty:
            logger.info(f"Период данных: с {df['date'].min()} по {df['date'].max()}")
            
            # Проверяем последние записи
            df['date'] = pd.to_datetime(df['date'])
            latest_date = df['date'].max()
            current_date = datetime.now()
            
            logger.info(f"Последняя запись: {latest_date.strftime('%Y-%m-%d')}")
            logger.info(f"Текущая дата: {current_date.strftime('%Y-%m-%d')}")
            
            # Проверяем, есть ли записи за последние 5 дней
            for i in range(5):
                check_date = current_date - timedelta(days=i)
                check_date_str = check_date.strftime('%Y-%m-%d')
                records_for_date = df[df['date'] == check_date_str]
                
                if not records_for_date.empty:
                    logger.info(f"✅ {check_date_str}: {len(records_for_date)} записей")
                else:
                    logger.warning(f"❌ {check_date_str}: нет записей")
        else:
            logger.warning("Альтернативный файл данных пуст")
    else:
        logger.error(f"❌ Файлы данных не найдены")
        logger.error(f"Проверенные пути: {ATTENDANCE_FILE}, {ALTERNATIVE_ATTENDANCE_FILE}")
    
    logger.info("=== КОНЕЦ ДИАГНОСТИКИ ===")

# Команда /diagnose
async def diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    await update.message.reply_text("🔍 Запуск диагностики данных...")
    
    # Запускаем диагностику
    diagnose_data_issue()
    
    # Получаем информацию о данных
    df = load_attendance_data()
    
    if df.empty:
        await update.message.reply_text(
            "❌ Проблема с данными:\n\n"
            "• Файл данных не найден или пуст\n"
            "• Проверьте логи для подробной информации"
        )
        return
    
    # Формируем отчет о состоянии данных
    df['date'] = pd.to_datetime(df['date'])
    latest_date = df['date'].max()
    current_date = datetime.now()
    
    message = "📊 Диагностика данных СКУД\n\n"
    message += f"📅 Всего записей: {len(df)}\n"
    message += f"📅 Период данных: {df['date'].min().strftime('%d.%m.%Y')} - {latest_date.strftime('%d.%m.%Y')}\n"
    message += f"👥 Уникальных сотрудников: {df['employee'].nunique()}\n\n"
    
    # Проверяем последние 5 дней
    message += "📈 Последние 5 дней:\n"
    missing_days = 0
    
    for i in range(5):
        check_date = current_date - timedelta(days=i)
        check_date_str = check_date.strftime('%Y-%m-%d')
        records_for_date = df[df['date'] == check_date_str]
        
        if not records_for_date.empty:
            message += f"✅ {check_date.strftime('%d.%m')}: {len(records_for_date)} записей\n"
        else:
            message += f"❌ {check_date.strftime('%d.%m')}: нет данных\n"
            missing_days += 1
    
    if missing_days > 0:
        message += f"\n⚠️ Отсутствуют данные за {missing_days} дней из последних 5"
    else:
        message += f"\n✅ Данные за последние 5 дней присутствуют"
    
    await update.message.reply_text(message)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    # Создаем клавиатуру с кнопками команд и Web App
    keyboard = [
        [InlineKeyboardButton("Отчеты через Web App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("Отчет за текущий месяц", callback_data="menu_report")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Добро пожаловать в бот системы СКУД!\n\n"
        "Доступные команды:\n"
        "• /report - получение отчета за текущий или предыдущий месяц\n"
        "• /diagnose - диагностика проблем с данными\n"
        "• /check_data - проверка данных в реальном времени\n"
        "• /add_employee <серийный_номер> <имя> - добавление нового сотрудника\n"
        "• /webapp - открыть отчеты через Web App\n\n"
        "💡 Используйте /check_data для проверки доступности данных за июль",
        reply_markup=reply_markup
    )

# Команда для открытия Web App
async def webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    # Создаем кнопку для открытия Web App
    keyboard = [[InlineKeyboardButton("Открыть отчеты", web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Нажмите кнопку для просмотра отчетов в Telegram Web App:",
        reply_markup=reply_markup
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
        ],
        [
            InlineKeyboardButton("Открыть отчеты через Web App", web_app=WebAppInfo(url=WEBAPP_URL))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Выберите период для отчета:", reply_markup=reply_markup)

# Команда /check_data
async def check_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    await update.message.reply_text("🔍 Проверка данных в реальном времени...")
    
    # Загружаем данные
    df = load_attendance_data()
    
    if df.empty:
        await update.message.reply_text("❌ Данные не найдены")
        return
    
    # Преобразуем даты
    df['date'] = pd.to_datetime(df['date'])
    
    # Получаем информацию о данных
    min_date = df['date'].min()
    max_date = df['date'].max()
    total_records = len(df)
    
    message = "📊 Проверка данных СКУД\n\n"
    message += f"📅 Всего записей: {total_records}\n"
    message += f"📅 Период: {min_date.strftime('%d.%m.%Y')} - {max_date.strftime('%d.%m.%Y')}\n\n"
    
    # Проверяем данные за июль 2025
    july_data = df[(df['date'].dt.year == 2025) & (df['date'].dt.month == 7)]
    
    if not july_data.empty:
        july_min = july_data['date'].min()
        july_max = july_data['date'].max()
        july_records = len(july_data)
        
        message += f"📈 Июль 2025:\n"
        message += f"• Записей: {july_records}\n"
        message += f"• Период: {july_min.strftime('%d.%m')} - {july_max.strftime('%d.%m')}\n\n"
        
        # Проверяем последние дни июля
        late_july_data = july_data[july_data['date'].dt.day >= 22]
        if not late_july_data.empty:
            late_dates = sorted(late_july_data['date'].unique())
            message += f"✅ Данные за 22-31 июля: {len(late_dates)} дней\n"
            message += f"📅 Даты: {', '.join([d.strftime('%d.%m') for d in late_dates])}\n"
        else:
            message += f"❌ НЕТ данных за 22-31 июля\n"
    else:
        message += f"❌ Нет данных за июль 2025\n"
    
    await update.message.reply_text(message)

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
        
        logger.info(f"Запрос отчета за {calendar.month_name[month]} {year}")
        await query.edit_message_text(f"Генерация отчета за {calendar.month_name[month]} {year}...")
        
        # Генерируем отчет
        excel_file, chart_file, period = generate_monthly_report(year, month)
        
        if excel_file is None:
            logger.warning(f"Не удалось сгенерировать отчет за {calendar.month_name[month]} {year}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Нет данных за {period}."
            )
            return
        
        logger.info(f"Отчет успешно сгенерирован: {excel_file}")
        
        # Загружаем данные для показа сводных цифр
        df = load_attendance_data()
        df['date'] = pd.to_datetime(df['date'])
        mask = (df['date'].dt.year == year) & (df['date'].dt.month == month)
        monthly_data = df[mask].copy()
        
        if not monthly_data.empty:
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
            
            # Создаем сообщение со сводными цифрами
            summary_message = f"📊 Сводные цифры за {period}:\n\n"
            summary_message += f"🕐 Общее вых: {weekend_total_hours:.1f} ч\n"
            summary_message += f"🕐 Общее будни: {weekday_total_hours:.1f} ч\n"
            summary_message += f"🕐 Общий итог: {total_hours:.1f} ч\n\n"
            summary_message += f"📈 Сотрудников: {monthly_data['employee'].nunique()}\n"
            summary_message += f"📅 Рабочих дней: {monthly_data['date'].nunique()}"
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=summary_message
            )
        
        # Отправляем Excel-файл
        with open(excel_file, 'rb') as file:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file,
                filename=os.path.basename(excel_file),
                caption=f"📋 Отчет посещаемости за {period}"
            )
        
        # Отправляем график
        with open(chart_file, 'rb') as file:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=file,
                caption=f"📊 График отработанных часов за {period}"
            )
    
    elif data == "menu_report":
        # Перенаправляем на команду report
        await report(update, context)

# Обработчик данных от Web App
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if ALLOWED_USERS and user_id not in ALLOWED_USERS:
        await update.message.reply_text("У вас нет доступа к этому боту.")
        logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
        return
    
    try:
        # Получаем данные от Web App
        data = json.loads(update.effective_message.web_app_data.data)
        logger.info(f"Получены данные от Web App: {data}")
        
        action = data.get('action')
        
        if action == 'generate_report':
            year = data.get('year')
            month = int(data.get('month'))
            report_type = data.get('report_type')
            
            await update.message.reply_text(f"Генерация отчета за {calendar.month_name[month]} {year}...")
            
            # Генерируем отчет
            excel_file, chart_file, period = generate_monthly_report(int(year), month)
            
            if excel_file is None:
                await update.message.reply_text(f"Нет данных за {period}.")
                return
            
            # Загружаем данные для показа сводных цифр
            df = load_attendance_data()
            df['date'] = pd.to_datetime(df['date'])
            mask = (df['date'].dt.year == int(year)) & (df['date'].dt.month == month)
            monthly_data = df[mask].copy()
            
            if not monthly_data.empty:
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
                
                # Создаем сообщение со сводными цифрами
                summary_message = f"📊 Сводные цифры за {period}:\n\n"
                summary_message += f"🕐 Общее вых: {weekend_total_hours:.1f} ч\n"
                summary_message += f"🕐 Общее будни: {weekday_total_hours:.1f} ч\n"
                summary_message += f"🕐 Общий итог: {total_hours:.1f} ч\n\n"
                summary_message += f"📈 Сотрудников: {monthly_data['employee'].nunique()}\n"
                summary_message += f"📅 Рабочих дней: {monthly_data['date'].nunique()}"
                
                await update.message.reply_text(summary_message)
            
            # Отправляем Excel-файл
            with open(excel_file, 'rb') as file:
                await context.bot.send_document(
                    chat_id=update.effective_message.chat_id,
                    document=file,
                    filename=os.path.basename(excel_file),
                    caption=f"📋 Отчет посещаемости за {period}"
                )
            
            # Отправляем график
            with open(chart_file, 'rb') as file:
                await context.bot.send_photo(
                    chat_id=update.effective_message.chat_id,
                    photo=file,
                    caption=f"График отработанных часов за {period}"
                )
        
        elif action == 'view_report':
            report_url = data.get('report_url')
            report_name = data.get('report_name')
            
            # Извлекаем имя файла из URL
            filename = report_name.strip()
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'reports')
            file_path = os.path.join(reports_dir, filename)
            
            if os.path.exists(file_path):
                # Отправляем файл пользователю
                with open(file_path, 'rb') as file:
                    await context.bot.send_document(
                        chat_id=update.effective_message.chat_id,
                        document=file,
                        filename=filename,
                        caption=f"Отчет: {filename}"
                    )
            else:
                # Если файл не найден, отправляем ссылку
                await update.message.reply_text(
                    f"Вы выбрали отчет: {report_name}\n"
                    f"Скачать можно по ссылке: {report_url}"
                )
        
        else:
            await update.message.reply_text(f"Неизвестное действие: {action}")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке данных от Web App: {str(e)}")
        await update.message.reply_text(f"Произошла ошибка при обработке данных: {str(e)}")

# Запуск бота
def main():
    # Проверяем, установлен ли токен
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("Пожалуйста, установите токен телеграм-бота в переменной TELEGRAM_TOKEN")
        return
    
    # Запускаем диагностику при старте
    logger.info("Запуск диагностики данных при старте бота...")
    diagnose_data_issue()
    
    # Создаем приложение
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("report", report))
    application.add_handler(CommandHandler("add_employee", add_employee))
    application.add_handler(CommandHandler("webapp", webapp))
    application.add_handler(CommandHandler("diagnose", diagnose)) # Добавляем обработчик для команды /diagnose
    application.add_handler(CommandHandler("check_data", check_data)) # Добавляем обработчик для команды /check_data
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработчик данных от Web App
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    
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