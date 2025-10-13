document.addEventListener('DOMContentLoaded', function() {
    const grid = document.getElementById('calendar-grid');
    const currentWeekDisplay = document.getElementById('current-week');
    const prevWeekBtn = document.getElementById('prev-week');
    const nextWeekBtn = document.getElementById('next-week');
    const modal = document.getElementById('booking-modal');
    const closeModalBtn = document.getElementById('close-button');
    const modalInfo = document.getElementById('modal-info');
    const bookingForm = document.getElementById('booking-form');
    const nomeInput = document.getElementById('nome');
    const ideiaInput = document.getElementById('ideia');
    const telefoneInput = document.getElementById('telefone');
    const imagemInput = document.getElementById('ideia-imagem');
    const fileNameSpan = document.getElementById('file-name');
    const alertModal = document.getElementById('alert-modal');
    const alertMessage = document.getElementById('alert-message');
    const alertCloseButton = document.getElementById('alert-close-button');
    const ctaButton = document.getElementById('cta-button');
    const calendarContainer = document.querySelector('.calendar-container');

    ctaButton.addEventListener('click', () => {
        calendarContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    imagemInput.addEventListener('change', () => {
        fileNameSpan.textContent = imagemInput.files.length > 0 ? imagemInput.files[0].name : 'Nenhum arquivo selecionado';
    });

    const API_URL = 'https://agendamento-server.onrender.com'; 
    const workHours = { start: 9, end: 21 };
    let currentDay = new Date();
    let alertCallback = null;

    function showCustomAlert(message, onConfirm = null) {
        alertMessage.textContent = message;
        alertModal.style.display = 'flex';
        alertCallback = onConfirm;
    }

    alertCloseButton.addEventListener('click', () => {
        alertModal.style.display = 'none';
        if (typeof alertCallback === 'function') { alertCallback(); }
    });

    function formatDate(date) {
        return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
    }

    async function renderCalendar(baseDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        grid.innerHTML = '';
        grid.classList.add('loading');
        const startOfPeriod = new Date(baseDate);
        startOfPeriod.setHours(0, 0, 0, 0);
        const endOfPeriod = new Date(startOfPeriod);
        endOfPeriod.setDate(startOfPeriod.getDate() + 2);

        const startDay = startOfPeriod.getDate();
        const endDay = endOfPeriod.getDate();
        let newHeaderText = '';
        if (startOfPeriod.getMonth() === endOfPeriod.getMonth()) {
            let monthName = startOfPeriod.toLocaleDateString('pt-BR', { month: 'long' });
            newHeaderText = `De ${startDay} a ${endDay} de ${monthName.charAt(0).toUpperCase() + monthName.slice(1)}`;
        } else {
            let startMonthName = startOfPeriod.toLocaleDateString('pt-BR', { month: 'long' });
            let endMonthName = endOfPeriod.toLocaleDateString('pt-BR', { month: 'long' });
            newHeaderText = `De ${startDay} de ${startMonthName.charAt(0).toUpperCase() + startMonthName.slice(1)} a ${endDay} de ${endMonthName.charAt(0).toUpperCase() + endMonthName.slice(1)}`;
        }
        currentWeekDisplay.textContent = newHeaderText;
        prevWeekBtn.disabled = startOfPeriod <= today;

        grid.insertAdjacentHTML('beforeend', `<div class="grid-header" style="border-left: none;"></div>`);
        const periodDays = [];
        for (let i = 0; i < 3; i++) {
            const day = new Date(startOfPeriod); day.setDate(startOfPeriod.getDate() + i); periodDays.push(day);
            const dayName = day.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '').toUpperCase();
            grid.insertAdjacentHTML('beforeend', `<div class="grid-header">${dayName}<br><span style="font-weight: 400; font-size: 0.9em;">${day.getDate()}</span></div>`);
        }
        try {
            const periodAvailability = await Promise.all(periodDays.map(day => fetch(`${API_URL}/api/horarios?date=${formatDate(day)}`).then(res => res.json())));
            for (let hour = workHours.start; hour < workHours.end; hour++) {
                for (let minutes of [0, 30]) {
                    const timeString = `${hour.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
                    grid.insertAdjacentHTML('beforeend', `<div class="time-label">${timeString}</div>`);
                    for (let dayIndex = 0; dayIndex < 3; dayIndex++) {
                        const currentDayInLoop = periodDays[dayIndex];
                        const availableSlotsForDay = periodAvailability[dayIndex];
                        let isPast = (currentDayInLoop < today) || (currentDayInLoop.getTime() === today.getTime() && (new Date().getHours() > hour || (new Date().getHours() === hour && new Date().getMinutes() >= minutes)));
                        const isAvailable = Array.isArray(availableSlotsForDay) && availableSlotsForDay.includes(timeString);
                        let slotText = 'Agendar'; let availabilityClass = '';
                        if (isPast) { slotText = '---'; availabilityClass = 'past-day'; } 
                        else if (!isAvailable) { slotText = 'Ocupado'; availabilityClass = 'unavailable'; }
                        grid.insertAdjacentHTML('beforeend', `<div class="time-slot ${availabilityClass}" data-date="${formatDate(currentDayInLoop)}" data-time="${timeString}">${slotText}</div>`);
                    }
                }
            }
        } catch (error) {
            grid.innerHTML = `<p style="color: #ff4d4d; grid-column: 1 / 5; text-align: center; padding: 20px;">Erro ao carregar horários. Verifique se o servidor backend está rodando.</p>`;
        } finally { grid.classList.remove('loading'); }
    }
    
    prevWeekBtn.addEventListener('click', () => { currentDay.setDate(currentDay.getDate() - 3); renderCalendar(currentDay); });
    nextWeekBtn.addEventListener('click', () => { currentDay.setDate(currentDay.getDate() + 3); renderCalendar(currentDay); });
    closeModalBtn.addEventListener('click', () => modal.style.display = 'none');
    modal.addEventListener('click', (event) => { if (event.target === modal) modal.style.display = 'none'; });

    grid.addEventListener('click', (event) => {
        const target = event.target;
        if (target.matches('.time-slot:not(.unavailable):not(.past-day)')) {
            const date = target.dataset.date; const time = target.dataset.time;
            const formattedDate = new Date(date + 'T00:00:00').toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
            modalInfo.textContent = `Você está agendando para ${formattedDate} às ${time}.`;
            bookingForm.dataset.date = date; bookingForm.dataset.time = time;
            bookingForm.reset(); fileNameSpan.textContent = 'Nenhum arquivo selecionado';
            modal.style.display = 'flex';
        }
    });

    telefoneInput.addEventListener('input', (evento) => {
        let valor = evento.target.value.replace(/\D/g, '').substring(0, 11);
        let valorFormatado = '';
        if (valor.length > 2) valorFormatado = `(${valor.substring(0, 2)}) ${valor.substring(2, 7)}-${valor.substring(7, 11)}`;
        else if (valor.length > 0) valorFormatado = `(${valor}`;
        evento.target.value = valorFormatado;
    });

    bookingForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (telefoneInput.value.replace(/\D/g, '').length < 10) { showCustomAlert('Por favor, insira um número de telefone válido com DDD.'); return; }
        
        const formData = new FormData();
        formData.append('date', bookingForm.dataset.date);
        formData.append('time', bookingForm.dataset.time);
        formData.append('nome', nomeInput.value);
        formData.append('telefone', telefoneInput.value);
        formData.append('ideia', ideiaInput.value);
        if (imagemInput.files.length > 0) formData.append('ideia-imagem', imagemInput.files[0]);

        const submitButton = bookingForm.querySelector('button');
        submitButton.textContent = 'Agendando...'; submitButton.disabled = true;
        try {
            const response = await fetch(`${API_URL}/api/agendar`, { method: 'POST', body: formData });
            if (!response.ok) { const errorData = await response.json(); throw new Error(errorData.error || 'Houve um erro.'); }
            const result = await response.json();
            modal.style.display = 'none';
            const mensagem = encodeURIComponent(`Olá! Confirmei meu agendamento para ${formData.get('date')} às ${formData.get('time')}. Meu nome é ${formData.get('nome')}.`);
            showCustomAlert("Agendamento confirmado! Redirecionando para o WhatsApp.", () => {
                renderCalendar(currentDay);
                window.location.href = `https://wa.me/${result.whatsappNumber}?text=${mensagem}`;
            });
        } catch (error) { showCustomAlert(error.message);
        } finally { submitButton.textContent = 'Confirmar Agendamento'; submitButton.disabled = false; }
    });
    
    renderCalendar(currentDay);

});
