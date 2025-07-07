#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import pandas as pd
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_close.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Настройки
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.csv')
DEFAULT_END_TIME = "17:00"  # Время автоматического закрытия дня

# Загрузка данных посещаемости
def load_attendance_data():
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE)
    else:
        return pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])

# Сохранение данных посещаемости
def save_attendance_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)

# Закрытие незавершенных дней
def close_unfinished_days():
    logger.info("Запуск автоматического закрытия незавершенных дней")
    
    # Загружаем данные посещаемости
    df = load_attendance_data()
    
    if df.empty:
        logger.info("Нет данных посещаемости")
        return
    
    # Получаем текущую дату
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Ищем записи за вчерашний день с приходом, но без ухода
    mask = (df['date'] == yesterday) & pd.notna(df['arrival']) & pd.isna(df['departure'])
    unfinished_count = mask.sum()
    
    if unfinished_count > 0:
        logger.info(f"Найдено {unfinished_count} незавершенных записей за {yesterday}")
        
        # Заполняем уход временем по умолчанию
        df.loc[mask, 'departure'] = DEFAULT_END_TIME
        
        # Сохраняем обновленные данные
        save_attendance_data(df)
        
        # Выводим информацию о закрытых записях
        closed_records = df[mask]
        for _, row in closed_records.iterrows():
            logger.info(f"Закрыта запись: {row['employee']} на {row['date']}, приход: {row['arrival']}, уход: {DEFAULT_END_TIME}")
    else:
        logger.info(f"Нет незавершенных записей за {yesterday}")

if __name__ == '__main__':
    close_unfinished_days() 