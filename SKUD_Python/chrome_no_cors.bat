@echo off
echo Запуск Chrome без CORS ограничений для тестирования СКУД...
echo ВНИМАНИЕ: Используйте только для тестирования!
echo.

:: Создаем временную папку для профиля
set TEMP_PROFILE=%TEMP%\chrome_test_profile

:: Запускаем Chrome с отключенными CORS
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="%TEMP_PROFILE%" --disable-web-security --disable-features=VizDisplayCompositor --disable-site-isolation-trials

echo Chrome запущен с отключенным CORS.
echo Теперь можно открыть test_attendance.html
pause 