from datetime import datetime, time, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import app, db
from app.models import Appointment, Client


if __name__ == '__main__':
    with app.app_context():
        db.engines[None] = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        db.create_all()
        client = Client(first_name='Elizabeth', last_name='Weber')
        db.session.add(client)
        db.session.flush()
        today = datetime.now().date()
        db.session.add(Appointment(client_id=client.id, date_time=datetime.combine(today, time(14)), description='Color', google_event_id='linked'))
        db.session.commit()
    day = today.isoformat()
    events = [
        {'id': 'linked', 'summary': 'Elizabeth Weber: Color', 'start': {'dateTime': f'{day}T14:00:00-03:00'}, 'end': {'dateTime': f'{day}T15:00:00-03:00'}},
        {'id': 'new', 'summary': 'Nuevo evento de Google', 'start': {'dateTime': f'{day}T16:00:00-03:00'}, 'end': {'dateTime': f'{day}T17:00:00-03:00'}},
        {'id': 'allday', 'summary': 'Recordatorio de Google', 'start': {'date': day}, 'end': {'date': (today + timedelta(days=1)).isoformat()}},
    ]

    @app.post('/__test/change')
    def change_event():
        events[1]['summary'] = 'Evento actualizado automaticamente'
        return '', 204

    with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.google_calendar_configured', return_value=True), patch('app.routes.google_watch_active', return_value=True), patch('app.routes.list_google_events', side_effect=lambda *args: events), patch('app.google_calendar_sync.calendar_service', return_value=object()):
        app.run(host='127.0.0.1', port=5056, threaded=False)
