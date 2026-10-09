document.addEventListener('DOMContentLoaded', () => {
    const element = document.getElementById('salon-calendar');
    if (!element) return;
    const error = document.getElementById('calendar-error');
    if (!window.FullCalendar) { error.hidden = false; return; }
    let appointments = [];
    let selectedDay = new Date();
    let loading = 0;
    const localDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    function renderAgenda() {
        document.getElementById('agenda-date').textContent = selectedDay.toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long' });
        const container = document.getElementById('agenda-items');
        container.replaceChildren();
        const items = appointments.filter(item => item.date === localDate(selectedDay)).sort((a, b) => a.time.localeCompare(b.time));
        if (!items.length) { container.textContent = 'No hay turnos para este d\u00eda.'; return; }
        items.forEach(item => {
            const link = document.createElement('a');
            link.className = 'dashboard-list-item';
            link.href = item.url;
            const time = document.createElement('time');
            time.textContent = item.allDay ? 'Todo el d\u00eda' : item.time;
            const details = document.createElement('div');
            const name = document.createElement('strong');
            name.textContent = item.client_name;
            const description = document.createElement('span');
            description.textContent = item.description;
            details.append(name, description);
            link.append(time, details);
            container.append(link);
        });
    }
    const calendar = new FullCalendar.Calendar(element, {
        locale: 'es', firstDay: 1, initialView: window.innerWidth < 640 ? 'timeGridDay' : 'timeGridWeek',
        headerToolbar: { left: 'prev,next today', center: 'title', right: 'timeGridDay,timeGridWeek,dayGridMonth' },
        buttonText: { today: 'Hoy', day: 'D\u00eda', week: 'Semana', month: 'Mes' },
        allDaySlot: true, allDayText: 'Todo el d\u00eda', nowIndicator: true, height: window.innerWidth < 640 ? 620 : 740,
        scrollTime: '09:00:00', slotMinTime: '07:00:00', slotMaxTime: '23:00:00',
        slotDuration: '00:30:00', eventDisplay: 'block', displayEventEnd: false,
        eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        slotLabelFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
        editable: true, eventDurationEditable: false,
        eventAllow: drop => !drop.allDay,
        events: async (info, success, failure) => {
            loading += 1;
            try {
                const automatic = Boolean(element.dataset.refreshUrl);
                const response = automatic ? await fetch(element.dataset.refreshUrl, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ start: localDate(info.start), end: localDate(info.end) })
                }) : await fetch(element.dataset.eventsUrl);
                if (!response.ok) throw new Error('No se pudieron cargar los turnos.');
                const result = await response.json();
                appointments = automatic ? result.events : result;
                const status = document.getElementById('google-sync-status');
                if (automatic && status) status.textContent = result.warning || 'Actualizado ' + new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
                error.hidden = true;
                success(appointments);
                renderAgenda();
            } catch (problem) { error.hidden = false; failure(problem); }
            finally { loading -= 1; }
        },
        datesSet: () => { selectedDay = calendar.getDate(); renderAgenda(); },
        dateClick: info => {
            const url = new URL(element.dataset.addUrl, window.location.origin);
            url.searchParams.set('date', localDate(info.date));
            url.searchParams.set('time', info.allDay ? '09:00' : info.date.toTimeString().slice(0, 5));
            window.location.assign(url);
        },
        eventClick: info => {
            info.jsEvent.preventDefault();
            if (info.event.extendedProps.source === 'google') window.open(info.event.url, '_blank', 'noopener,noreferrer');
            else window.location.assign(info.event.url);
        },
        eventDrop: async info => {
            const dateTime = `${localDate(info.event.start)}T${info.event.start.toTimeString().slice(0, 5)}`;
            if (!window.confirm('Reprogramar el turno a ' + info.event.start.toLocaleString('es-AR') + '?')) { info.revert(); return; }
            try {
                const response = await fetch(info.event.extendedProps.reschedule_url, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date_time: dateTime })
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'No se pudo reprogramar el turno.');
                if (result.warning) displayMessage(result.warning, 'info');
                calendar.refetchEvents();
            } catch (problem) { info.revert(); displayMessage(problem.message, 'danger'); }
        }
    });
    calendar.render();
    if (element.dataset.refreshUrl) {
        const refresh = () => { if (!document.hidden && !loading) calendar.refetchEvents(); };
        const timer = window.setInterval(refresh, 60000);
        document.addEventListener('visibilitychange', refresh);
        window.addEventListener('pagehide', () => window.clearInterval(timer), { once: true });
    }
});
