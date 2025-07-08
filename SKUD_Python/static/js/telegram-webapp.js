// Telegram Web App Integration
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация Telegram Web App
    const tgApp = window.Telegram?.WebApp;
    
    // Если открыто не в Telegram Web App, выходим
    if (!tgApp) {
        console.log('Не запущено в Telegram Web App');
        return;
    }
    
    console.log('Telegram Web App запущен');
    
    // Уведомляем Telegram, что веб-приложение готово
    tgApp.ready();
    
    // Получаем данные пользователя
    const user = tgApp.initDataUnsafe?.user;
    if (user) {
        console.log(`Пользователь: ${user.username || user.first_name}`);
    }
    
    // Применяем тему Telegram к нашему приложению
    if (tgApp.themeParams) {
        document.documentElement.style.setProperty('--tg-theme-bg-color', tgApp.themeParams.bg_color || '#ffffff');
        document.documentElement.style.setProperty('--tg-theme-text-color', tgApp.themeParams.text_color || '#222222');
        document.documentElement.style.setProperty('--tg-theme-hint-color', tgApp.themeParams.hint_color || '#999999');
        document.documentElement.style.setProperty('--tg-theme-link-color', tgApp.themeParams.link_color || '#2678b6');
        document.documentElement.style.setProperty('--tg-theme-button-color', tgApp.themeParams.button_color || '#50a8eb');
        document.documentElement.style.setProperty('--tg-theme-button-text-color', tgApp.themeParams.button_text_color || '#ffffff');
    }
    
    // Адаптируем UI для Telegram Web App
    adaptUIForTelegramWebApp();
    
    // Добавляем кнопку "Назад" для закрытия Web App
    addBackButton();
    
    // Добавляем обработчики для кнопок отчетов
    setupReportButtons();
});

// Адаптация UI для Telegram Web App
function adaptUIForTelegramWebApp() {
    // Скрываем навбар, так как он не нужен в Telegram Web App
    const navbar = document.querySelector('nav.navbar');
    if (navbar) {
        navbar.style.display = 'none';
    }
    
    // Скрываем футер
    const footer = document.querySelector('footer.footer');
    if (footer) {
        footer.style.display = 'none';
    }
    
    // Добавляем отступ снизу для safe area
    document.body.style.paddingBottom = '20px';
    
    // Добавляем класс к body для специальных стилей
    document.body.classList.add('tg-webapp');
}

// Добавление кнопки "Назад"
function addBackButton() {
    const tgApp = window.Telegram?.WebApp;
    if (!tgApp) return;
    
    const container = document.querySelector('.container');
    if (!container) return;
    
    const backButton = document.createElement('button');
    backButton.innerText = 'Закрыть';
    backButton.className = 'btn btn-outline-secondary mt-3';
    backButton.style.position = 'fixed';
    backButton.style.bottom = '20px';
    backButton.style.left = '50%';
    backButton.style.transform = 'translateX(-50%)';
    backButton.style.zIndex = '1000';
    
    backButton.addEventListener('click', function() {
        tgApp.close();
    });
    
    document.body.appendChild(backButton);
}

// Настройка кнопок для отчетов с отправкой данных обратно в бот
function setupReportButtons() {
    const tgApp = window.Telegram?.WebApp;
    
    // Находим кнопки скачивания отчетов
    const reportButtons = document.querySelectorAll('a[href*="download_report"]');
    
    reportButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const reportUrl = this.getAttribute('href');
            const reportName = this.parentElement.querySelector('span').innerText;
            
            console.log("Клик по кнопке скачивания:", reportName);
            
            // Если запущено в Telegram Web App, отправляем данные боту
            if (tgApp) {
                console.log("Отправка данных в Telegram Web App");
                
                // Отправляем данные о выбранном отчете обратно в бот
                tgApp.sendData(JSON.stringify({
                    action: 'view_report',
                    report_url: window.location.origin + reportUrl,
                    report_name: reportName
                }));
                
                // Открываем файл в новой вкладке
                window.open(reportUrl, '_blank');
            }
            
            // Не используем preventDefault, чтобы стандартное поведение ссылки также работало
        });
    });
    
    // Перехватываем отправку формы генерации отчета
    const reportForm = document.querySelector('form[action*="generate_report"]');
    if (reportForm) {
        reportForm.addEventListener('submit', function(e) {
            console.log("Отправка формы генерации отчета");
            
            const formData = new FormData(this);
            const year = formData.get('year');
            const month = formData.get('month');
            const reportType = formData.get('report_type');
            
            // Если запущено в Telegram Web App, отправляем данные боту
            if (tgApp) {
                console.log("Отправка данных генерации отчета в Telegram Web App");
                
                // Отправляем данные о запросе генерации отчета обратно в бот
                tgApp.sendData(JSON.stringify({
                    action: 'generate_report',
                    year: year,
                    month: month,
                    report_type: reportType
                }));
            }
            
            // Не используем preventDefault, форма будет отправлена обычным способом
        });
    }
} 