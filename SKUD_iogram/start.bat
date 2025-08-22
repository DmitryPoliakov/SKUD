@echo off
echo Запуск СКУД бота на aiogram...
echo =====================================
echo Тестовый токен: 8044045216:AAEamiCHNsr5jZaXi7NFKPe47BoWWkgucbM
echo Для локального тестирования
echo =====================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден в PATH
    pause
    exit /b 1
)

REM Проверяем наличие requirements.txt
if not exist requirements.txt (
    echo Ошибка: файл requirements.txt не найден
    pause
    exit /b 1
)

REM Устанавливаем зависимости
echo Установка зависимостей...
pip install -r requirements.txt

if errorlevel 1 (
    echo Ошибка при установке зависимостей
    pause
    exit /b 1
)

echo.
echo Запуск бота...
python run.py

pause
