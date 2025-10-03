document.addEventListener('DOMContentLoaded', function() {
    // Referências aos elementos
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
    const alertModal = document.getElementById('alert-modal');
    const alertMessage = document.getElementById('alert-message');
    const alertCloseButton = document.getElementById('alert-close-button');

    const API_URL = 'https://agendamento-ql82.onrender.com'; 
    const workHours = { start: 9, end: 21 };
    let currentDay = new Date();

    // Função para exibir o alerta customizado
    let alertCallback = null;
    function showCustomAlert(message, onConfirm = null) {
        alertMessage.textContent = message;
        alertModal.style.display = 'flex';
        alertCallback = onConfirm;
    }

    // Evento para fechar o modal de alerta
    alertCloseButton.addEventListener('click', () => {
        alertModal.style.display = 'none';
        if (typeof alertCallback === 'function') {
            alertCallback();
        }
    });

    function formatDate(date) {
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    async function renderCalendar(baseDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        grid.innerHTML = '';
        grid.classList.add('loading');
        // Mostra 3 dias a partir do baseDate
        const startOfPeriod = new Date(baseDate);
        startOfPeriod.setHours(0, 0, 0, 0);
        const endOfPeriod = new Date(startOfPeriod);
        endOfPeriod.setDate(startOfPeriod.getDate() + 2); // +2 para totalizar 3 dias

        currentWeekDisplay.textContent = `Dias de ${startOfPeriod.toLocaleDateString('pt-BR')} a ${endOfPeriod.toLocaleDateString('pt-BR')}`;
        
        prevWeekBtn.disabled = startOfPeriod <= today;

        // Cabeçalho: vazio + nomes dos dias
        grid.insertAdjacentHTML('beforeend', `<div class="grid-header"></div>`);
        const periodDays = [];
        for (let i = 0; i < 3; i++) {
            const day = new Date(startOfPeriod);
            day.setDate(startOfPeriod.getDate() + i);
            periodDays.push(day);
            const dayName = day.toLocaleDateString('pt-BR', { weekday: 'short' }).toUpperCase();
            const dayNumber = day.getDate();
            grid.insertAdjacentHTML('beforeend', `<div class="grid-header">${dayName}<br>${dayNumber}</div>`);
        }
        try {
            const periodAvailability = [];
            for (const day of periodDays) {
                const response = await fetch(`${API_URL}/api/horarios?date=${formatDate(day)}`);
                if (!response.ok) throw new Error(`Falha ao buscar horários para ${formatDate(day)}`);
                const availabilityForDay = await response.json();
                periodAvailability.push(availabilityForDay);
            }
            for (let hour = workHours.start; hour < workHours.end; hour++) {
                // Itera pelos minutos dentro da hora (00 e 30)
                for (let minutes of [0, 30]) {
                    const timeString = `${hour.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;

                    // Primeira coluna: horário
                    grid.insertAdjacentHTML('beforeend', `<div class="time-label">${timeString}</div>`);

                    // Colunas dos dias
                    for (let dayIndex = 0; dayIndex < 3; dayIndex++) {
                        const currentDayInLoop = periodDays[dayIndex];
                        const availableSlotsForDay = periodAvailability[dayIndex];

                        let isPast = currentDayInLoop < today;
                        if (!isPast && currentDayInLoop.getTime() === today.getTime()) {
                            // Se for hoje, bloqueia horários já passados
                            const now = new Date();
                            const slotHour = hour;
                            const slotMinutes = minutes;
                            if (now.getHours() > slotHour || (now.getHours() === slotHour && now.getMinutes() >= slotMinutes)) {
                                isPast = true;
                            }
                        }
                        const isAvailable = availableSlotsForDay.includes(timeString);

                        const dateString = formatDate(currentDayInLoop);
                        let availabilityClass = '';
                        let slotText = 'Agendar';

                        if (isPast) {
                            availabilityClass = 'past-day';
                            slotText = '---';
                        } else if (!isAvailable) {
                            availabilityClass = 'unavailable';
                            slotText = 'Ocupado';
                        }

                        grid.insertAdjacentHTML('beforeend', 
                            `<div class="time-slot ${availabilityClass}" data-date="${dateString}" data-time="${timeString}">
                                ${slotText}
                            </div>`
                        );
                    }
                }
            }
        } catch (error) {
            grid.innerHTML = `<p style="color: red; grid-column: 1 / 5; text-align: center;">Erro ao carregar horários. Verifique o servidor backend e a conexão.</p>`;
            console.error("Erro ao renderizar calendário:", error);
        } finally {
            grid.classList.remove('loading');
        }
    }
    
    prevWeekBtn.addEventListener('click', () => {
        currentDay.setDate(currentDay.getDate() - 3);
        renderCalendar(currentDay);
    });

    nextWeekBtn.addEventListener('click', () => {
        currentDay.setDate(currentDay.getDate() + 3);
        renderCalendar(currentDay);
    });

    function closeModal() {
        modal.style.display = 'none';
    }
    closeModalBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeModal();
        }
    });

    grid.addEventListener('click', (event) => {
        const target = event.target;
        if (target.classList.contains('time-slot') && !target.classList.contains('unavailable') && !target.classList.contains('past-day')) {
            const date = target.dataset.date;
            const time = target.dataset.time;
            modalInfo.textContent = `Você está agendando para o dia ${date} às ${time}.`;
            bookingForm.dataset.date = date;
            bookingForm.dataset.time = time;
            bookingForm.reset();
            modal.style.display = 'flex';
        }
    });

    function formatarTelefone(evento) {
        let input = evento.target;
        let valor = input.value.replace(/\D/g, '');
        valor = valor.substring(0, 11);
        
        let valorFormatado = '';
        if (valor.length > 0) {
            valorFormatado = '(' + valor.substring(0, 2);
        }
        if (valor.length > 2) {
            const partePrincipal = valor.substring(2);
            if (partePrincipal.length > 5) {
                valorFormatado += ') ' + partePrincipal.substring(0, 5) + '-' + partePrincipal.substring(5, 9);
            } else {
                valorFormatado += ') ' + partePrincipal;
            }
        }
        input.value = valorFormatado;
    }

    telefoneInput.addEventListener('input', formatarTelefone);

    bookingForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const numeroLimpo = telefoneInput.value.replace(/\D/g, '');
        if (numeroLimpo.length < 10 || numeroLimpo.length > 11) {
            showCustomAlert('Por favor, insira um número de telefone válido com DDD.');
            telefoneInput.focus();
            return;
        }

        const bookingData = {
            date: bookingForm.dataset.date,
            time: bookingForm.dataset.time,
            nome: nomeInput.value,
            telefone: telefoneInput.value,
            ideia: ideiaInput.value
        };

        const submitButton = bookingForm.querySelector('button');
        submitButton.textContent = 'Agendando...';
        submitButton.disabled = true;

        try {
            const response = await fetch(`${API_URL}/api/agendar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(bookingData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                showCustomAlert(errorData.error || 'Houve um erro ao tentar agendar. Tente novamente.');
                return;
            }

            const result = await response.json();
            closeModal();

            const whatsappNumber = result.whatsappNumber;
            const mensagem = `Olá! Acabei de confirmar meu agendamento para o dia ${bookingData.date} às ${bookingData.time}. Meu nome é ${bookingData.nome}.`;
            const mensagemCodificada = encodeURIComponent(mensagem);
            const whatsappUrl = `https://wa.me/${whatsappNumber}?text=${mensagemCodificada}`;

            showCustomAlert(
                "Agendamento confirmado! Você será redirecionado para o WhatsApp para finalizar os detalhes.",
                () => {
                    renderCalendar(currentDay);
                    window.location.href = whatsappUrl;
                }
            );
        } catch (error) {
            showCustomAlert('Houve um erro ao tentar agendar. Tente novamente.');
            console.error("Erro ao agendar:", error);
        } finally {
            submitButton.textContent = 'Confirmar Agendamento';
            submitButton.disabled = false;
        }
    });
    
    renderCalendar(currentDay);
});