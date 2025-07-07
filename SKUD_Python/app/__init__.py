# Пустой файл для обозначения директории как пакет Python 

from flask import Flask
import os
import json
import pandas as pd
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import importlib.util

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10485760, backupCount=5),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

template_path = os.environ.get('FLASK_TEMPLATE_PATH', '../templates')
static_path = os.environ.get('FLASK_STATIC_PATH', '../static')
app = Flask(__name__, 
           template_folder=template_path,
           static_folder=static_path)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ATTENDANCE_FILE = os.path.join(DATA_DIR, 'attendance.csv')
EMPLOYEES_FILE = os.path.join(DATA_DIR, 'employees.json')

os.makedirs(DATA_DIR, exist_ok=True)

def load_employees():
    if os.path.exists(EMPLOYEES_FILE):
        with open(EMPLOYEES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        default_employees = {
            "992BEE97": "Поляков",
            "894046B8": "Тарасов",
            "E79DF8A4": "Карта МИР 4635",
            "0A711B71": "Карта Прокатут",
            "92C2001D": "Карта МИР 0514",
            "E9DBA5A3": "Шура"
        }
        with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_employees, f, ensure_ascii=False, indent=4)
        return default_employees

def save_new_employee(serial, name):
    employees = load_employees()
    employees[serial] = name
    with open(EMPLOYEES_FILE, 'w', encoding='utf-8') as f:
        json.dump(employees, f, ensure_ascii=False, indent=4)
    logger.info(f"Добавлен новый сотрудник: {name} с картой {serial}")
    return True

def load_attendance_data():
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE)
    else:
        df = pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])
        df.to_csv(ATTENDANCE_FILE, index=False)
        return df

def save_attendance_data(df):
    df.to_csv(ATTENDANCE_FILE, index=False)

def notify_admin(message):
    try:
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_bot.py')
        spec = importlib.util.spec_from_file_location("telegram_bot", module_path)
        telegram_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(telegram_bot)
        telegram_bot.notify_admin(message)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {str(e)}") 