const EMPLOYEES = {
  "0102030405060708": "Иванов",
  "0908070605040302": "Петров"
};

const MIN_INTERVAL_MINUTES = 1; // Минимальный интервал между срабатываниями
const WEEKEND_DAYS = [0, 6]; // Воскресенье (0) и Суббота (6)
const DEFAULT_END_TIME = "17:00"; // Время автоматического закрытия дня

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Attendance");
  var data = JSON.parse(e.postData.contents);
  var serial = data.serial;
  var time = data.time; // Формат: "2025-06-25 05:43"
  
  // Проверка сотрудника
  if (!(serial in EMPLOYEES)) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "unknown",
      message: "Неизвестный ключ: " + serial
    })).setMimeType(ContentService.MimeType.JSON);
  }
  var name = EMPLOYEES[serial];
  
  // Парсинг времени и даты
  var dateTime = new Date(time);
  var dateStr = Utilities.formatDate(dateTime, "GMT+3", "yyyy-MM-dd");
  var timeStr = Utilities.formatDate(dateTime, "GMT+3", "HH:mm");
  
  // Поиск столбца для текущей даты
  var headers = sheet.getRange(1, 2, 1, sheet.getLastColumn() - 1).getValues()[0];
  var colIndex = headers.indexOf(Utilities.formatDate(dateTime, "GMT+3", "E yyyy-MM-dd"));
  if (colIndex == -1) {
    // Создать новый столбец, если дата не найдена
    colIndex = sheet.getLastColumn();
    sheet.getRange(1, colIndex + 1).setValue(Utilities.formatDate(dateTime, "GMT+3", "E yyyy-MM-dd"));
  }
  colIndex += 2; // Смещение на первый столбец (Фамилия)
  
  // Поиск строки сотрудника
  var names = sheet.getRange(2, 1, sheet.getLastRow() - 1, 1).getValues().flat();
  var rowIndex = names.indexOf(name);
  if (rowIndex == -1) {
    // Добавить нового сотрудника
    rowIndex = sheet.getLastRow() + 1;
    sheet.getRange(rowIndex, 1).setValue(name);
  } else {
    rowIndex += 2; // Смещение на заголовок
  }
  
  // Проверка последнего срабатывания (фильтрация ложных)
  var lastTimeKey = serial + "_" + dateStr;
  var scriptProperties = PropertiesService.getScriptProperties();
  var lastTime = scriptProperties.getProperty(lastTimeKey);
  if (lastTime) {
    var lastDateTime = new Date(lastTime);
    var timeDiff = (dateTime - lastDateTime) / (1000 * 60); // Разница в минутах
    if (timeDiff < MIN_INTERVAL_MINUTES) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "ignored",
        message: "Повторное срабатывание. Прошло менее " + MIN_INTERVAL_MINUTES + " минут",
        employee: name,
        lastTime: Utilities.formatDate(lastDateTime, "GMT+3", "HH:mm:ss")
      })).setMimeType(ContentService.MimeType.JSON);
    }
  }
  scriptProperties.setProperty(lastTimeKey, time);
  
  // Определение прихода/ухода
  var currentValue = sheet.getRange(rowIndex, colIndex).getValue();
  var eventType = "";
  
  if (currentValue == "" || !currentValue.includes("Приход")) {
    // Записать приход
    sheet.getRange(rowIndex, colIndex).setValue("Приход: " + timeStr + ", Уход: -");
    eventType = "приход";
  } else {
    // Обновить уход
    var arrivalTime = currentValue.split(",")[0].split(": ")[1];
    sheet.getRange(rowIndex, colIndex).setValue("Приход: " + arrivalTime + ", Уход: " + timeStr);
    eventType = "уход";
  }
  
  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    message: "Данные успешно записаны",
    employee: name,
    event: eventType,
    time: timeStr,
    date: dateStr
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Генерирует статистический отчет за указанный месяц
 * @param {number} year - Год (например, 2025)
 * @param {number} month - Месяц (1-12)
 */
function generateMonthlyReport(year, month) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var attendanceSheet = ss.getSheetByName("Attendance");
  
  // Создаем или очищаем лист отчета
  var reportSheet = ss.getSheetByName("MonthlyReport");
  if (!reportSheet) {
    reportSheet = ss.insertSheet("MonthlyReport");
  } else {
    reportSheet.clear();
  }
  
  // Заголовки отчета
  reportSheet.getRange(1, 1).setValue("Сотрудник");
  reportSheet.getRange(1, 2).setValue("Всего часов");
  reportSheet.getRange(1, 3).setValue("Часов в выходные");
  reportSheet.getRange(1, 4).setValue("Рабочих дней");
  reportSheet.getRange(1, 5).setValue("Средняя продолжительность дня");
  
  // Получаем данные из листа посещаемости
  var headers = attendanceSheet.getRange(1, 1, 1, attendanceSheet.getLastColumn()).getValues()[0];
  var data = attendanceSheet.getRange(2, 1, attendanceSheet.getLastRow() - 1, attendanceSheet.getLastColumn()).getValues();
  
  // Обрабатываем каждого сотрудника
  var row = 2;
  for (var i = 0; i < data.length; i++) {
    var employeeName = data[i][0];
    if (!employeeName) continue;
    
    var totalHours = 0;
    var weekendHours = 0;
    var workDays = 0;
    
    // Проходим по всем датам
    for (var j = 1; j < headers.length; j++) {
      var dateHeader = headers[j];
      if (!dateHeader || typeof dateHeader !== 'string') continue;
      
      // Проверяем, что дата относится к указанному месяцу и году
      var match = dateHeader.match(/\d{4}-(\d{2})-(\d{2})/);
      if (!match) continue;
      
      var dateObj = new Date(dateHeader.replace(/^[A-Za-zА-Яа-я]{1,2}\s/, ""));
      if (dateObj.getFullYear() !== year || dateObj.getMonth() + 1 !== month) continue;
      
      var attendance = data[i][j];
      if (!attendance || typeof attendance !== 'string' || !attendance.includes("Приход") || !attendance.includes("Уход")) continue;
      
      // Извлекаем время прихода и ухода
      var arrivalTime = attendance.split(",")[0].split(": ")[1];
      var departureTime = attendance.split(",")[1].split(": ")[1];
      
      if (departureTime === "-") continue; // Пропускаем, если нет времени ухода
      
      // Рассчитываем часы
      var hours = calculateHours(dateObj, arrivalTime, departureTime);
      totalHours += hours;
      
      // Проверяем, является ли день выходным
      if (WEEKEND_DAYS.includes(dateObj.getDay())) {
        weekendHours += hours;
      }
      
      workDays++;
    }
    
    // Записываем данные в отчет
    reportSheet.getRange(row, 1).setValue(employeeName);
    reportSheet.getRange(row, 2).setValue(Math.round(totalHours * 10) / 10); // Округляем до 1 десятичного знака
    reportSheet.getRange(row, 3).setValue(Math.round(weekendHours * 10) / 10);
    reportSheet.getRange(row, 4).setValue(workDays);
    reportSheet.getRange(row, 5).setValue(workDays > 0 ? Math.round((totalHours / workDays) * 10) / 10 : 0);
    
    row++;
  }
  
  // Форматирование
  reportSheet.autoResizeColumns(1, 5);
  var headerRange = reportSheet.getRange(1, 1, 1, 5);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#f3f3f3");
  
  return reportSheet.getSheetId();
}

/**
 * Рассчитывает количество отработанных часов за день
 * @param {Date} date - Дата
 * @param {string} arrivalTime - Время прихода (HH:MM)
 * @param {string} departureTime - Время ухода (HH:MM)
 * @return {number} - Количество часов
 */
function calculateHours(date, arrivalTime, departureTime) {
  var arrivalDate = new Date(date);
  var departureDate = new Date(date);
  
  var arrivalParts = arrivalTime.split(":");
  arrivalDate.setHours(parseInt(arrivalParts[0], 10), parseInt(arrivalParts[1], 10), 0, 0);
  
  var departureParts = departureTime.split(":");
  departureDate.setHours(parseInt(departureParts[0], 10), parseInt(departureParts[1], 10), 0, 0);
  
  // Если уход раньше прихода, предполагаем, что уход был на следующий день
  if (departureDate < arrivalDate) {
    departureDate.setDate(departureDate.getDate() + 1);
  }
  
  var diffMs = departureDate - arrivalDate;
  var diffHours = diffMs / (1000 * 60 * 60);
  
  return diffHours;
}

/**
 * Создает меню для удобного запуска отчетов
 */
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('СКУД')
      .addItem('Отчет за текущий месяц', 'generateCurrentMonthReport')
      .addItem('Отчет за произвольный месяц', 'showReportDialog')
      .addItem('Закрыть незавершенные дни', 'closeUnfinishedDays')
      .addToUi();
}

/**
 * Генерирует отчет за текущий месяц
 */
function generateCurrentMonthReport() {
  var today = new Date();
  generateMonthlyReport(today.getFullYear(), today.getMonth() + 1);
  SpreadsheetApp.getUi().alert('Отчет за текущий месяц сформирован!');
}

/**
 * Показывает диалог для выбора месяца и года
 */
function showReportDialog() {
  var ui = SpreadsheetApp.getUi();
  var result = ui.prompt(
    'Выберите месяц и год',
    'Введите месяц и год в формате ММ.ГГГГ (например, 06.2025):',
    ui.ButtonSet.OK_CANCEL
  );
  
  var button = result.getSelectedButton();
  var text = result.getResponseText();
  
  if (button == ui.Button.OK) {
    var parts = text.split('.');
    if (parts.length === 2) {
      var month = parseInt(parts[0], 10);
      var year = parseInt(parts[1], 10);
      
      if (!isNaN(month) && !isNaN(year) && month >= 1 && month <= 12) {
        generateMonthlyReport(year, month);
        ui.alert('Отчет сформирован!');
      } else {
        ui.alert('Неверный формат. Пожалуйста, используйте формат ММ.ГГГГ');
      }
    } else {
      ui.alert('Неверный формат. Пожалуйста, используйте формат ММ.ГГГГ');
    }
  }
}

/**
 * Закрывает незавершенные рабочие дни и выделяет их красным цветом
 * Запускается автоматически по расписанию в 23:59
 */
function closeUnfinishedDays() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Attendance");
  
  // Получаем текущую дату
  var today = new Date();
  var dateStr = Utilities.formatDate(today, "GMT+3", "E yyyy-MM-dd");
  
  // Находим столбец для текущей даты
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colIndex = headers.indexOf(dateStr);
  if (colIndex == -1) return; // Если сегодняшней даты нет в таблице, выходим
  
  // Получаем все данные посещаемости за сегодня
  var data = sheet.getRange(2, colIndex + 1, sheet.getLastRow() - 1, 1).getValues();
  var ranges = [];
  
  // Проходим по всем сотрудникам
  for (var i = 0; i < data.length; i++) {
    var attendance = data[i][0];
    
    // Проверяем, есть ли запись о приходе без ухода
    if (attendance && typeof attendance === 'string' && 
        attendance.includes("Приход") && attendance.includes("Уход: -")) {
      
      var rowIndex = i + 2; // +2 для учета заголовка и смещения индекса
      var cell = sheet.getRange(rowIndex, colIndex + 1);
      
      // Извлекаем время прихода
      var arrivalTime = attendance.split(",")[0].split(": ")[1];
      
      // Обновляем ячейку, устанавливая уход в 17:00
      cell.setValue("Приход: " + arrivalTime + ", Уход: " + DEFAULT_END_TIME);
      
      // Выделяем ячейку красным цветом
      cell.setBackground("#ffcccc");
      
      // Добавляем комментарий
      cell.setNote("Автоматически закрыто системой в 23:59");
    }
  }
}

/**
 * Настраивает ежедневный триггер для закрытия незавершенных дней
 * Запускается один раз при установке скрипта
 */
function setupDailyTrigger() {
  // Удаляем существующие триггеры с таким же именем функции
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'closeUnfinishedDays') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  
  // Создаем новый триггер на 23:59 каждый день
  ScriptApp.newTrigger('closeUnfinishedDays')
      .timeBased()
      .everyDays(1)
      .atHour(23)
      .nearMinute(59)
      .create();
}