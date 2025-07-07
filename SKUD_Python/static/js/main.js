// Функция для форматирования даты
function formatDate(dateString) {
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return new Date(dateString).toLocaleDateString('ru-RU', options);
}

// Функция для форматирования времени
function formatTime(timeString) {
    return timeString;
}

// Функция для расчета отработанных часов
function calculateHours(arrival, departure) {
    if (!arrival || !departure) return null;
    
    const [arrivalHours, arrivalMinutes] = arrival.split(':').map(Number);
    const [departureHours, departureMinutes] = departure.split(':').map(Number);
    
    let hours = departureHours - arrivalHours;
    let minutes = departureMinutes - arrivalMinutes;
    
    if (minutes < 0) {
        hours -= 1;
        minutes += 60;
    }
    
    if (hours < 0) {
        hours += 24; // Предполагаем, что уход был на следующий день
    }
    
    return hours + minutes / 60;
}

// Инициализация всплывающих подсказок
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});