#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import calendar
import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import io

from config import config

# Настройка matplotlib для работы без GUI
matplotlib.use('Agg')

logger = logging.getLogger(__name__)

class DataManager:
    """Класс для работы с данными СКУД"""
    
    def __init__(self):
        self.data_dir = config.DATA_DIR
        self.attendance_file = config.ATTENDANCE_FILE
        self.employees_file = config.EMPLOYEES_FILE
        self.reports_dir = config.REPORTS_DIR
        
        # Альтернативный путь (если запускается из корневой директории проекта)
        self.alternative_data_dir = os.path.join(os.getcwd(), 'data')
        self.alternative_attendance_file = os.path.join(self.alternative_data_dir, 'attendance.csv')
        
        self._log_paths()

    def _log_paths(self):
        """Логирование путей для отладки"""
        logger.info(f"Текущая директория: {os.getcwd()}")
        logger.info(f"Директория данных: {self.data_dir}")
        logger.info(f"Файл посещаемости: {self.attendance_file}")
        logger.info(f"Альтернативный файл: {self.alternative_attendance_file}")
        logger.info(f"Директория отчетов: {self.reports_dir}")
        logger.info(f"Основной файл существует: {os.path.exists(self.attendance_file)}")
        logger.info(f"Альтернативный файл существует: {os.path.exists(self.alternative_attendance_file)}")

    def load_employees(self) -> dict:
        """Загружает список сотрудников из JSON файла"""
        if os.path.exists(self.employees_file):
            with open(self.employees_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Создаем файл с сотрудниками по умолчанию (текущая корректная структура)
            default_employees = {
                "992BEE97": "Поляков Павел",
                "894046B8": "Тарасов Никита",
                "92C2001D": "Поляков Дмитрий", 
                "E9DBA5A3": "Шура",
                "32AABBD6": "Поляков Павел",
                "296DD1A3": "Пущинский Марк",
                "97D3A7DD": "Палкин Семён"
            }
            self.save_employees(default_employees)
            return default_employees

    def save_employees(self, employees: dict):
        """Сохраняет список сотрудников в JSON файл"""
        with open(self.employees_file, 'w', encoding='utf-8') as f:
            json.dump(employees, f, ensure_ascii=False, indent=4)

    def add_employee(self, serial: str, name: str) -> bool:
        """Добавляет нового сотрудника"""
        try:
            employees = self.load_employees()
            employees[serial.upper()] = name
            self.save_employees(employees)
            logger.info(f"Добавлен новый сотрудник: {name} с картой {serial}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении сотрудника: {e}")
            return False

    def load_attendance_data(self) -> pd.DataFrame:
        """Загружает данные посещаемости с автоматическим поиском файла"""
        logger.info(f"Загрузка данных из файла: {self.attendance_file}")
        
        # Сначала пробуем основной путь
        if os.path.exists(self.attendance_file):
            df = pd.read_csv(self.attendance_file)
            logger.info(f"Файл найден по основному пути, загружено {len(df)} записей")
            if not df.empty:
                logger.info(f"Период данных в файле: с {df['date'].min()} по {df['date'].max()}")
                self._log_recent_records(df)
            return df
        
        # Если основной путь не работает, пробуем альтернативный
        logger.info(f"Основной файл не найден, пробуем альтернативный: {self.alternative_attendance_file}")
        if os.path.exists(self.alternative_attendance_file):
            df = pd.read_csv(self.alternative_attendance_file)
            logger.info(f"Файл найден по альтернативному пути, загружено {len(df)} записей")
            if not df.empty:
                logger.info(f"Период данных в файле: с {df['date'].min()} по {df['date'].max()}")
                self._log_recent_records(df)
            return df
        
        # Если файл не найден ни по одному пути, создаем пустой DataFrame
        logger.warning(f"Файл данных не найден ни по одному из путей")
        logger.warning(f"Проверенные пути: {self.attendance_file}, {self.alternative_attendance_file}")
        df = pd.DataFrame(columns=['date', 'employee', 'arrival', 'departure'])
        os.makedirs(os.path.dirname(self.attendance_file), exist_ok=True)
        df.to_csv(self.attendance_file, index=False)
        return df

    def _log_recent_records(self, df: pd.DataFrame):
        """Логирует последние 5 записей для диагностики (только при включенном debug)"""
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Последние 5 записей:")
            for i, row in df.tail(5).iterrows():
                logger.debug(f"  {row['date']} - {row['employee']} - {row['arrival']} - {row['departure']}")

    def generate_monthly_report(self, year: int, month: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Генерирует месячный отчет в Excel и PNG формате"""
        df = self.load_attendance_data()
        
        # Отладочная информация только при debug режиме
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Загружено всего записей: {len(df)}")
            if not df.empty:
                logger.debug(f"Период данных: с {df['date'].min()} по {df['date'].max()}")
                unique_dates = sorted(df['date'].unique())
                logger.debug(f"Уникальные даты в данных: {unique_dates[:10]}...")  # Показываем первые 10
        
        # Преобразуем даты
        df['date'] = pd.to_datetime(df['date'])
        
        # Фильтруем по году и месяцу
        mask = (df['date'].dt.year == year) & (df['date'].dt.month == month)
        monthly_data = df[mask].copy()
        
        logger.info(f"Найдено записей за {calendar.month_name[month]} {year}: {len(monthly_data)}")
        
        if monthly_data.empty:
            logger.warning(f"Нет данных за {calendar.month_name[month]} {year}")
            return None, None, None
        
        # Показываем диапазон дат в отфильтрованных данных (только в debug режиме)
        if not monthly_data.empty and logger.isEnabledFor(logging.DEBUG):
            min_date = monthly_data['date'].min()
            max_date = monthly_data['date'].max()
            logger.debug(f"Период данных в отчете: с {min_date.strftime('%Y-%m-%d')} по {max_date.strftime('%Y-%m-%d')}")
        
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
        
        # Логирование только основной информации
        logger.info(f"Отчет за {calendar.month_name[month]} {year}: {len(summary)} сотрудников, {total_hours:.1f} часов")
        
        # Создаем Excel-файл
        month_name = calendar.month_name[month]
        file_name = f"attendance_report_{year}_{month:02d}_{month_name}.xlsx"
        file_path = os.path.join(self.reports_dir, file_name)
        
        self._create_excel_report(monthly_data, summary, file_path, year, month, 
                                weekend_total_hours, weekday_total_hours, total_hours)
        
        # Создаем график
        chart_file = self._create_chart(summary, year, month, 
                                      weekend_total_hours, weekday_total_hours, total_hours)
        
        logger.info(f"Отчет сгенерирован: {file_path}")
        return file_path, chart_file, f"{month_name} {year}"

    def _create_excel_report(self, monthly_data, summary, file_path, year, month,
                           weekend_total_hours, weekday_total_hours, total_hours):
        """Создает Excel отчет"""
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

    def _create_chart(self, summary, year, month, weekend_total_hours, weekday_total_hours, total_hours):
        """Создает график для визуализации (временно отключено)"""
        # Создаем фиктивный файл графика
        chart_file = os.path.join(self.reports_dir, f"chart_{year}_{month:02d}.png")
        
        # Создаем пустой PNG файл (1x1 пиксель)
        try:
            import base64
            # Минимальный PNG файл в base64
            png_data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')
            with open(chart_file, 'wb') as f:
                f.write(png_data)
        except:
            # Если не получилось, создаем текстовый файл
            with open(chart_file, 'w') as f:
                f.write("График временно отключен")
        
        return chart_file

    def get_data_statistics(self) -> dict:
        """Возвращает статистику по данным"""
        df = self.load_attendance_data()
        
        if df.empty:
            return {
                'total_records': 0,
                'period': None,
                'employees_count': 0,
                'recent_days': []
            }
        
        # Преобразуем даты
        df['date'] = pd.to_datetime(df['date'])
        
        # Базовая статистика
        stats = {
            'total_records': len(df),
            'period': {
                'start': df['date'].min().strftime('%d.%m.%Y'),
                'end': df['date'].max().strftime('%d.%m.%Y')
            },
            'employees_count': df['employee'].nunique(),
            'recent_days': []
        }
        
        # Проверяем последние 5 дней
        current_date = datetime.now()
        for i in range(5):
            check_date = current_date - timedelta(days=i)
            check_date_str = check_date.strftime('%Y-%m-%d')
            records_for_date = df[df['date'] == check_date_str]
            
            stats['recent_days'].append({
                'date': check_date.strftime('%d.%m'),
                'records_count': len(records_for_date),
                'has_data': len(records_for_date) > 0
            })
        
        return stats

    def diagnose_data(self) -> str:
        """Проводит диагностику данных и возвращает отчет"""
        logger.info("=== ДИАГНОСТИКА ДАННЫХ ===")
        
        # Проверяем пути
        logger.info(f"Текущая директория: {os.getcwd()}")
        logger.info(f"Директория данных: {self.data_dir}")
        logger.info(f"Файл посещаемости: {self.attendance_file}")
        
        report = "🔍 Диагностика данных СКУД\n\n"
        
        # Проверяем существование файлов
        if os.path.exists(self.attendance_file):
            file_size = os.path.getsize(self.attendance_file)
            report += f"✅ Основной файл данных найден\n"
            report += f"📁 Размер файла: {file_size} байт\n\n"
            
            # Читаем данные
            df = pd.read_csv(self.attendance_file)
            report += f"📊 Загружено записей: {len(df)}\n"
            
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                latest_date = df['date'].max()
                current_date = datetime.now()
                
                report += f"📅 Период данных: {df['date'].min().strftime('%d.%m.%Y')} - {latest_date.strftime('%d.%m.%Y')}\n"
                report += f"📅 Последняя запись: {latest_date.strftime('%d.%m.%Y')}\n\n"
                
                # Проверяем последние 5 дней
                report += "📈 Последние 5 дней:\n"
                missing_days = 0
                
                for i in range(5):
                    check_date = current_date - timedelta(days=i)
                    check_date_str = check_date.strftime('%Y-%m-%d')
                    records_for_date = df[df['date'] == check_date_str]
                    
                    if not records_for_date.empty:
                        report += f"✅ {check_date.strftime('%d.%m')}: {len(records_for_date)} записей\n"
                    else:
                        report += f"❌ {check_date.strftime('%d.%m')}: нет данных\n"
                        missing_days += 1
                
                if missing_days > 0:
                    report += f"\n⚠️ Отсутствуют данные за {missing_days} дней из последних 5"
                else:
                    report += f"\n✅ Данные за последние 5 дней присутствуют"
            else:
                report += "❌ Файл данных пуст"
                
        elif os.path.exists(self.alternative_attendance_file):
            report += f"✅ Альтернативный файл данных найден\n"
            # Аналогичная проверка для альтернативного файла
        else:
            report += f"❌ Файлы данных не найдены\n"
            report += f"🔍 Проверенные пути:\n"
            report += f"• {self.attendance_file}\n"
            report += f"• {self.alternative_attendance_file}\n"
        
        logger.info("=== КОНЕЦ ДИАГНОСТИКИ ===")
        return report

# Глобальный экземпляр менеджера данных
data_manager = DataManager()
