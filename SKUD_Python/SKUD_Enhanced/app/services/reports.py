#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Сервис для генерации отчетов посещаемости
"""

import os
import calendar
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from sqlalchemy.orm import Session
from loguru import logger

from ..config import config
from ..models import Employee, AttendanceEvent, DailyAttendance, EventType


class ReportService:
    """Сервис для генерации отчетов"""
    
    def __init__(self):
        # Настройка matplotlib для русского языка
        plt.rcParams['font.family'] = ['DejaVu Sans', 'Arial Unicode MS', 'Tahoma']
        sns.set_style("whitegrid")
        sns.set_palette("husl")
    
    async def generate_monthly_report(
        self, 
        db: Session, 
        year: int, 
        month: int
    ) -> Tuple[Optional[str], Optional[str], str]:
        """
        Генерирует месячный отчет посещаемости
        
        Returns:
            Tuple[excel_file_path, chart_file_path, period_name]
        """
        try:
            month_name = calendar.month_name[month]
            period_name = f"{month_name} {year}"
            
            logger.info(f"Генерация отчета за {period_name}")
            
            # Получаем данные
            data = self._get_monthly_data(db, year, month)
            
            if not data:
                logger.warning(f"Нет данных за {period_name}")
                return None, None, period_name
            
            # Создаем DataFrame
            df = pd.DataFrame(data)
            
            # Генерируем Excel отчет
            excel_file = await self._create_excel_report(df, year, month, period_name)
            
            # Генерируем график
            chart_file = await self._create_chart(df, year, month, period_name)
            
            logger.success(f"Отчет за {period_name} успешно создан")
            return excel_file, chart_file, period_name
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            raise
    
    def _get_monthly_data(self, db: Session, year: int, month: int) -> List[Dict[str, Any]]:
        """Получает данные посещаемости за месяц"""
        try:
            # Формируем период
            start_date = f"{year:04d}-{month:02d}-01"
            
            # Последний день месяца
            last_day = calendar.monthrange(year, month)[1]
            end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
            
            # Запрос всех событий за месяц
            events = db.query(AttendanceEvent).join(Employee).filter(
                AttendanceEvent.event_date >= start_date,
                AttendanceEvent.event_date <= end_date
            ).order_by(
                AttendanceEvent.event_date,
                Employee.name,
                AttendanceEvent.event_time
            ).all()
            
            if not events:
                return []
            
            # Группируем события по дням и сотрудникам
            daily_data = {}
            
            for event in events:
                key = (event.employee.name, event.event_date)
                
                if key not in daily_data:
                    daily_data[key] = {
                        'employee': event.employee.name,
                        'date': event.event_date,
                        'arrival': None,
                        'departure': None,
                        'hours_worked': 0,
                        'is_weekend': self._is_weekend(event.event_date)
                    }
                
                if event.event_type == EventType.ARRIVAL:
                    daily_data[key]['arrival'] = event.event_time.strftime('%H:%M')
                elif event.event_type == EventType.DEPARTURE:
                    daily_data[key]['departure'] = event.event_time.strftime('%H:%M')
            
            # Вычисляем отработанные часы
            result = []
            for record in daily_data.values():
                if record['arrival'] and record['departure']:
                    try:
                        arrival_time = datetime.strptime(
                            f"{record['date']} {record['arrival']}", 
                            '%Y-%m-%d %H:%M'
                        )
                        departure_time = datetime.strptime(
                            f"{record['date']} {record['departure']}", 
                            '%Y-%m-%d %H:%M'
                        )
                        
                        # Если уход раньше прихода, значит уход на следующий день
                        if departure_time < arrival_time:
                            departure_time += timedelta(days=1)
                        
                        duration = departure_time - arrival_time
                        record['hours_worked'] = round(duration.total_seconds() / 3600, 2)
                        
                    except Exception as e:
                        logger.warning(f"Ошибка расчета времени работы: {e}")
                        record['hours_worked'] = 0
                
                result.append(record)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения данных за месяц: {e}")
            return []
    
    def _is_weekend(self, date_str: str) -> bool:
        """Проверяет, является ли день выходным"""
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            return date_obj.weekday() >= 5  # Суббота=5, Воскресенье=6
        except:
            return False
    
    async def _create_excel_report(
        self, 
        df: pd.DataFrame, 
        year: int, 
        month: int, 
        period_name: str
    ) -> str:
        """Создает Excel отчет"""
        try:
            # Подготавливаем директорию
            reports_dir = config.REPORTS_DIR
            reports_dir.mkdir(exist_ok=True)
            
            # Имя файла
            filename = f"attendance_report_{year}_{month:02d}_{calendar.month_name[month]}.xlsx"
            filepath = reports_dir / filename
            
            with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                # Сводный отчет
                summary = self._create_summary_data(df)
                summary.to_excel(writer, sheet_name='Сводный отчет', index=False)
                
                # Детальный отчет
                detailed = self._prepare_detailed_data(df)
                detailed.to_excel(writer, sheet_name='Детальный отчет', index=False)
                
                # Получаем объекты для форматирования
                workbook = writer.book
                
                # Форматирование сводного отчета
                if 'Сводный отчет' in writer.sheets:
                    self._format_summary_sheet(writer.sheets['Сводный отчет'], workbook)
                
                # Форматирование детального отчета
                if 'Детальный отчет' in writer.sheets:
                    self._format_detailed_sheet(writer.sheets['Детальный отчет'], workbook)
            
            logger.info(f"Excel отчет создан: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Ошибка создания Excel отчета: {e}")
            raise
    
    def _create_summary_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создает сводные данные по сотрудникам"""
        if df.empty:
            return pd.DataFrame()
        
        summary = df.groupby('employee').agg({
            'date': 'nunique',  # Количество рабочих дней
            'hours_worked': ['sum', 'mean', 'count'],  # Сумма, среднее, количество
        }).round(2)
        
        # Сглаживаем MultiIndex колонки
        summary.columns = ['Рабочих дней', 'Всего часов', 'Средние часы', 'Записей']
        summary = summary.reset_index()
        summary.columns = ['Сотрудник', 'Рабочих дней', 'Всего часов', 'Средние часы', 'Записей']
        
        return summary
    
    def _prepare_detailed_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Подготавливает детальные данные"""
        if df.empty:
            return pd.DataFrame()
        
        detailed = df.copy()
        detailed['Дата'] = pd.to_datetime(detailed['date']).dt.strftime('%d.%m.%Y')
        detailed['День недели'] = pd.to_datetime(detailed['date']).dt.day_name()
        
        # Переименовываем колонки
        detailed = detailed.rename(columns={
            'employee': 'Сотрудник',
            'arrival': 'Приход',
            'departure': 'Уход',
            'hours_worked': 'Часов',
            'is_weekend': 'Выходной'
        })
        
        # Выбираем нужные колонки
        columns = ['Дата', 'День недели', 'Сотрудник', 'Приход', 'Уход', 'Часов', 'Выходной']
        detailed = detailed[columns]
        
        return detailed.sort_values(['Дата', 'Сотрудник'])
    
    def _format_summary_sheet(self, worksheet, workbook):
        """Форматирует лист сводного отчета"""
        try:
            # Форматы
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1,
                'align': 'center'
            })
            
            number_format = workbook.add_format({'num_format': '0.00'})
            
            # Заголовки
            for col in range(5):  # 5 колонок в сводном отчете
                worksheet.write(0, col, worksheet.table[0][col], header_format)
            
            # Ширина колонок
            worksheet.set_column('A:A', 20)  # Сотрудник
            worksheet.set_column('B:E', 12)  # Остальные колонки
            
        except Exception as e:
            logger.warning(f"Ошибка форматирования сводного отчета: {e}")
    
    def _format_detailed_sheet(self, worksheet, workbook):
        """Форматирует лист детального отчета"""
        try:
            # Форматы
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1,
                'align': 'center'
            })
            
            weekend_format = workbook.add_format({'bg_color': '#FFCCCC'})
            
            # Заголовки
            for col in range(7):  # 7 колонок в детальном отчете
                worksheet.write(0, col, worksheet.table[0][col], header_format)
            
            # Ширина колонок
            worksheet.set_column('A:A', 12)  # Дата
            worksheet.set_column('B:B', 15)  # День недели
            worksheet.set_column('C:C', 20)  # Сотрудник
            worksheet.set_column('D:F', 10)  # Приход, Уход, Часов
            worksheet.set_column('G:G', 10)  # Выходной
            
        except Exception as e:
            logger.warning(f"Ошибка форматирования детального отчета: {e}")
    
    async def _create_chart(
        self, 
        df: pd.DataFrame, 
        year: int, 
        month: int, 
        period_name: str
    ) -> Optional[str]:
        """Создает график отработанных часов"""
        try:
            if df.empty:
                return None
            
            # Подготавливаем данные для графика
            summary = df.groupby('employee')['hours_worked'].sum().sort_values(ascending=True)
            
            if summary.empty:
                return None
            
            # Создаем график
            plt.figure(figsize=(12, 8))
            
            # Горизонтальная диаграмма
            bars = plt.barh(range(len(summary)), summary.values)
            
            # Настройка осей
            plt.yticks(range(len(summary)), summary.index)
            plt.xlabel('Отработанные часы')
            plt.title(f'Отработанные часы за {period_name}', fontsize=14, fontweight='bold')
            
            # Добавляем значения на столбцы
            for i, (name, hours) in enumerate(summary.items()):
                plt.text(hours + max(summary) * 0.01, i, f'{hours:.1f}ч', 
                        va='center', fontweight='bold')
            
            # Цвета столбцов
            colors = plt.cm.Set3(range(len(summary)))
            for bar, color in zip(bars, colors):
                bar.set_color(color)
            
            # Сетка
            plt.grid(True, axis='x', alpha=0.3)
            
            # Настройка layout
            plt.tight_layout()
            
            # Сохраняем
            chart_filename = f"chart_{year}_{month:02d}.png"
            chart_filepath = config.REPORTS_DIR / chart_filename
            
            plt.savefig(chart_filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"График создан: {chart_filepath}")
            return str(chart_filepath)
            
        except Exception as e:
            logger.error(f"Ошибка создания графика: {e}")
            return None
    
    async def generate_weekly_report(self, db: Session, start_date: datetime) -> Dict[str, Any]:
        """Генерирует недельный отчет"""
        try:
            end_date = start_date + timedelta(days=7)
            
            # Получаем события за неделю
            events = db.query(AttendanceEvent).join(Employee).filter(
                AttendanceEvent.event_date >= start_date.strftime('%Y-%m-%d'),
                AttendanceEvent.event_date < end_date.strftime('%Y-%m-%d')
            ).order_by(AttendanceEvent.event_time).all()
            
            # Группируем по дням
            daily_stats = {}
            for i in range(7):
                date = start_date + timedelta(days=i)
                date_str = date.strftime('%Y-%m-%d')
                daily_stats[date_str] = {
                    'date': date.strftime('%d.%m.%Y'),
                    'weekday': date.strftime('%A'),
                    'arrivals': 0,
                    'departures': 0,
                    'unique_employees': set()
                }
            
            # Заполняем статистику
            for event in events:
                if event.event_date in daily_stats:
                    daily_stats[event.event_date]['unique_employees'].add(event.employee.name)
                    
                    if event.event_type == EventType.ARRIVAL:
                        daily_stats[event.event_date]['arrivals'] += 1
                    elif event.event_type == EventType.DEPARTURE:
                        daily_stats[event.event_date]['departures'] += 1
            
            # Преобразуем set в count
            for stats in daily_stats.values():
                stats['unique_employees'] = len(stats['unique_employees'])
            
            return {
                'period': f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
                'daily_stats': list(daily_stats.values()),
                'total_events': len(events),
                'total_employees': len(set(event.employee.name for event in events))
            }
            
        except Exception as e:
            logger.error(f"Ошибка генерации недельного отчета: {e}")
            raise 