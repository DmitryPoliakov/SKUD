const EMPLOYEES = {
  "992BEE97": "Поляков",
  "894046B8": "Тарасов",
  "E79DF8A4": "Карта МИР 4635",
  "0A711B71": "Карта Прокатут",
  "92C2001D": "Карта МИР 0514",
  
};

const MIN_INTERVAL_MINUTES = 1; // Минимальный интервал между срабатываниями
const WEEKEND_DAYS = [0, 6]; // Воскресенье (0) и Суббота (6)
const DEFAULT_END_TIME = "17:00"; // Время автоматического закрытия дня
const TIMEZONE = "GMT+5"; // Часовой пояс для всего скрипта

/**
 * Функция, которая выполняется при загрузке скрипта
 */
function doGet() {
  return HtmlService.createHtmlOutput('SKUD API работает нормально');
}

function doPost(e) {
  Logger.log("doPost вызван с параметрами: " + JSON.stringify(e));
  
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Attendance");
  if (!sheet) {
    sheet = ss.insertSheet("Attendance");
    sheet.getRange(1, 1).setValue("Сотрудники");
    Logger.log("Создан новый лист Attendance");
  }

  if (!e || !e.postData || !e.postData.contents) {
    Logger.log("e is undefined or no data");
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Нет данных в запросе"
    })).setMimeType(ContentService.MimeType.JSON);
  }

  var data;
  try {
    data = JSON.parse(e.postData.contents);
    Logger.log("Данные запроса: " + JSON.stringify(data));
  } catch (error) {
    Logger.log("Error parsing JSON: " + error.message);
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Ошибка парсинга JSON: " + error.message
    })).setMimeType(ContentService.MimeType.JSON);
  }

  var serial = data.serial;
  var time = data.time;
  Logger.log("Получен запрос для серийного номера: " + serial + ", время: " + time);
  
  if (!(serial in EMPLOYEES)) {
    Logger.log("Неизвестный ключ: " + serial);
    return ContentService.createTextOutput(JSON.stringify({
      status: "unknown",
      message: "Неизвестный ключ: " + serial
    })).setMimeType(ContentService.MimeType.JSON);
  }
  var name = EMPLOYEES[serial];
  Logger.log("Сотрудник: " + name);
  var dateTime = new Date(time.replace(/-/g, '/'));
  var dateStr = Utilities.formatDate(dateTime, TIMEZONE, "d-MMM-yyyy"); // Например, "4-Jul-2025"
  var weekDay = Utilities.formatDate(dateTime, TIMEZONE, "EEEE");
  var timeStr = Utilities.formatDate(dateTime, TIMEZONE, "HH:mm");
  Logger.log("Дата: " + dateStr + ", День недели: " + weekDay + ", Время: " + timeStr);

  // --- Поиск или добавление столбцов для даты ---
  var lastCol = sheet.getLastColumn();
  var dateCols = [];
  Logger.log("Поиск столбцов для даты: " + dateStr + ", Последний столбец: " + lastCol);
  for (var col = 2; col <= lastCol; col++) {
    var val = sheet.getRange(1, col).getValue();
    if (val instanceof Date) {
      val = Utilities.formatDate(val, TIMEZONE, "d-MMM-yyyy");
    }
    if (val == dateStr) {
      dateCols = [col, col + 1];
      break;
    }
  }

  if (dateCols.length === 0) {
    Logger.log("Date " + dateStr + " not found, creating new columns");
    dateCols = [lastCol + 1, lastCol + 2];
    sheet.insertColumnsAfter(lastCol, 2);
    sheet.getRange(1, dateCols[0], 1, 2).merge().setValue(dateStr);
    sheet.getRange(2, dateCols[0], 1, 2).merge().setValue(weekDay);
    sheet.getRange(3, dateCols[0]).setValue("Приход");
    sheet.getRange(3, dateCols[1]).setValue("Уход");
  }

  // --- Поиск или добавление строки сотрудника ---
  var lastRow = sheet.getLastRow();
  var names = [];
  if (lastRow >= 4) {
    names = sheet.getRange(4, 1, lastRow - 3, 1).getValues().flat();
  }
  var rowIndex = names.indexOf(name);
  if (rowIndex === -1) {
    rowIndex = names.length;
    sheet.getRange(4 + rowIndex, 1).setValue(name);
  }
  var sheetRow = 4 + rowIndex;

  // --- Проверка существующих записей для текущей даты ---
  var existingRow = -1;
  for (var i = 4; i <= lastRow; i++) {
    if (sheet.getRange(i, 1).getValue() === name) {
      var arrival = sheet.getRange(i, dateCols[0]).getValue();
      var departure = sheet.getRange(i, dateCols[1]).getValue();
      if (arrival || departure) {
        existingRow = i;
        Logger.log("Found existing row for " + name + " at row " + existingRow + " for date " + dateStr);
        break;
      }
    }
  }

  if (existingRow !== -1) {
    // Если запись для этой даты уже существует, используем её
    sheetRow = existingRow;
    Logger.log("Using existing row at " + sheetRow + " for " + name + " on " + dateStr);
  } else {
    // Если записи для этой даты нет, создаем новую строку
    sheetRow = 4 + rowIndex;
    Logger.log("Creating new row at " + sheetRow + " for " + name + " on " + dateStr);
  }

  // --- Проверка последнего срабатывания ---
  var scriptProperties = PropertiesService.getScriptProperties();
  var lastTimeKey = serial + "_" + dateStr;
  var lastTime = scriptProperties.getProperty(lastTimeKey);
  if (lastTime) {
    var lastDateTime = new Date(lastTime.replace(/-/g, '/'));
    var timeDiff = (dateTime - lastDateTime) / (1000 * 60);
    if (timeDiff < MIN_INTERVAL_MINUTES) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "ignored",
        message: "Повторное срабатывание. Прошло менее " + MIN_INTERVAL_MINUTES + " минут",
        employee: name,
        lastTime: Utilities.formatDate(lastDateTime, TIMEZONE, "HH:mm:ss")
      })).setMimeType(ContentService.MimeType.JSON);
    }
  }
  scriptProperties.setProperty(lastTimeKey, time);

  // --- Запись прихода/ухода ---
  var arrivalCell = sheet.getRange(sheetRow, dateCols[0]);
  var departureCell = sheet.getRange(sheetRow, dateCols[1]);
  var arrival = arrivalCell.getValue();
  var departure = departureCell.getValue();
  Logger.log("Текущие значения для строки " + sheetRow + ": Приход = " + arrival + ", Уход = " + departure);
  
  var eventType = "";
  if (!arrival) {
    arrivalCell.setValue(timeStr);
    eventType = "приход";
    Logger.log("Записан приход в ячейку " + sheetRow + "," + dateCols[0] + ": " + timeStr);
  } else if (!departure) {
    departureCell.setValue(timeStr);
    eventType = "уход";
    Logger.log("Записан уход в ячейку " + sheetRow + "," + dateCols[1] + ": " + timeStr);
  } else {
    departureCell.setValue(timeStr);
    eventType = "уход (повтор)";
    Logger.log("Записан повторный уход в ячейку " + sheetRow + "," + dateCols[1] + ": " + timeStr);
  }

  Logger.log("Формирую ответ: сотрудник = " + name + ", событие = " + eventType + ", время = " + timeStr);
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
  var sheet = ss.getSheetByName("Attendance");
  var reportSheet = ss.getSheetByName("MonthlyReport");
  if (!reportSheet) {
    reportSheet = ss.insertSheet("MonthlyReport");
  } else {
    reportSheet.clear();
  }
  
  // Заголовки отчета
  reportSheet.getRange(1, 1).setValue("Сотрудник");
  reportSheet.getRange(1, 2).setValue("Всего часов");
  reportSheet.getRange(1, 3).setValue("Рабочих дней");
  reportSheet.getRange(1, 4).setValue("Средняя продолжительность дня");
  
  var lastCol = sheet.getLastColumn();
  var lastRow = sheet.getLastRow();
  var names = sheet.getRange(4, 1, Math.max(0, lastRow - 3), 1).getValues().flat();
  var rowReport = 2;
  for (var i = 0; i < names.length; i++) {
    var name = names[i];
    if (!name) continue;
    var totalHours = 0;
    var workDays = 0;
    for (var col = 2; col <= lastCol; col += 2) {
      var dateVal = sheet.getRange(1, col).getValue();
      if (!dateVal) continue;
      var dateObj = new Date(dateVal);
      if (dateObj.getFullYear() !== year || (dateObj.getMonth() + 1) !== month) continue;
      var arrival = sheet.getRange(4 + i, col).getValue();
      var departure = sheet.getRange(4 + i, col + 1).getValue();
      if (arrival && departure) {
        // Преобразуем значения в строки перед использованием split
        var arrivalStr = String(arrival);
        var departureStr = String(departure);
        var arrivalParts = arrivalStr.split(":");
        var departureParts = departureStr.split(":");
        var arrivalDate = new Date(dateObj);
        var departureDate = new Date(dateObj);
        
        // Добавляем проверки на корректность формата времени
        if (arrivalParts.length >= 2 && departureParts.length >= 2) {
          var arrivalHours = parseInt(arrivalParts[0], 10);
          var arrivalMinutes = parseInt(arrivalParts[1], 10);
          var departureHours = parseInt(departureParts[0], 10);
          var departureMinutes = parseInt(departureParts[1], 10);
          
          // Проверяем, что все значения являются числами
          if (!isNaN(arrivalHours) && !isNaN(arrivalMinutes) && 
              !isNaN(departureHours) && !isNaN(departureMinutes)) {
            arrivalDate.setHours(arrivalHours, arrivalMinutes, 0, 0);
            departureDate.setHours(departureHours, departureMinutes, 0, 0);
            
            if (departureDate < arrivalDate) {
              departureDate.setDate(departureDate.getDate() + 1);
            }
            
            var diffMs = departureDate - arrivalDate;
            var diffHours = diffMs / (1000 * 60 * 60);
            totalHours += diffHours;
            workDays++;
          }
        }
      }
    }
    reportSheet.getRange(rowReport, 1).setValue(name);
    reportSheet.getRange(rowReport, 2).setValue(Math.round(totalHours * 100) / 100);
    reportSheet.getRange(rowReport, 3).setValue(workDays);
    reportSheet.getRange(rowReport, 4).setValue(workDays > 0 ? Math.round((totalHours / workDays) * 100) / 100 : 0);
    rowReport++;
  }
  
  reportSheet.autoResizeColumns(1, 4);
  var headerRange = reportSheet.getRange(1, 1, 1, 4);
  headerRange.setFontWeight("bold");
  headerRange.setBackground("#f3f3f3");
  
  return reportSheet.getSheetId();
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
  
  var today = new Date();
  var dateStr = Utilities.formatDate(today, TIMEZONE, "d-MMM-yyyy");
  
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colIndex = -1;
  
  // Ищем столбец с текущей датой
  for (var col = 2; col <= sheet.getLastColumn(); col++) {
    var val = sheet.getRange(1, col).getValue();
    if (val instanceof Date) {
      val = Utilities.formatDate(val, TIMEZONE, "d-MMM-yyyy");
    }
    if (val == dateStr) {
      colIndex = col - 1; // Корректируем индекс для соответствия массиву headers
      break;
    }
  }
  
  if (colIndex == -1) return;
  
  // Получаем столбцы для прихода и ухода
  var arrivalCol = colIndex + 1;
  var departureCol = colIndex + 2;
  
  // Проверяем все строки с сотрудниками
  for (var row = 4; row <= sheet.getLastRow(); row++) {
    var arrival = sheet.getRange(row, arrivalCol).getValue();
    var departure = sheet.getRange(row, departureCol).getValue();
    
    // Если есть приход, но нет ухода
    if (arrival && !departure) {
      var cell = sheet.getRange(row, departureCol);
      cell.setValue(DEFAULT_END_TIME);
      cell.setBackground("#ffcccc");
      cell.setNote("Автоматически закрыто системой в 23:59");
      Logger.log("Closed day for employee at row " + row);
    }
  }
}

/**
 * Настраивает ежедневный триггер для закрытия незавершенных дней
 */
function setupDailyTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'closeUnfinishedDays') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('closeUnfinishedDays')
      .timeBased()
      .everyDays(1)
      .atHour(23)
      .nearMinute(59)
      .create();
}