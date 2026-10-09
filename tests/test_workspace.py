import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from app import app, db
from app.models import Client, Appointment


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = app.app_context()
        cls.context.push()
        cls.original_engine = db.engines[None]
        db.engines[None] = create_engine('sqlite:///:memory:')

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.engines[None].dispose()
        db.engines[None] = cls.original_engine
        cls.context.pop()

    def setUp(self):
        db.create_all()
        self.client = Client(first_name='Ana', last_name='Perez')
        db.session.add(self.client)
        db.session.flush()
        self.turn = Appointment(client_id=self.client.id, date_time=datetime(2026, 10, 8, 10), description='Corte')
        db.session.add(self.turn)
        db.session.commit()
        self.browser = app.test_client()
        self.connection_patch = patch('app.routes.google_calendar_connected', return_value=False)
        self.connection_patch.start()
        self.duration_patch = patch.dict('os.environ', {'GOOGLE_CALENDAR_EVENT_MINUTES': '60'})
        self.duration_patch.start()

    def tearDown(self):
        self.connection_patch.stop()
        self.duration_patch.stop()
        db.session.remove()
        db.drop_all()

    def test_pages_and_new_appointment_prefill(self):
        for path in ['/', '/clients', '/appointments/calendar', f'/clients/{self.client.id}']:
            self.assertEqual(self.browser.get(path).status_code, 200, path)
        response = self.browser.get('/appointments/add?date=2026-10-09&time=14:30')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'2026-10-09T14:30', response.data)
        self.assertIn(b'Ana Perez', response.data)

    def test_event_links_and_duration(self):
        event = self.browser.get('/api/appointments').get_json()[0]
        self.assertEqual(event['end'], '2026-10-08T11:00:00')
        self.assertIn('/appointments/edit/', event['url'])
        self.assertIn('/reschedule', event['reschedule_url'])

    def test_reschedule_persists_and_rejects_overlaps(self):
        other = Appointment(client_id=self.client.id, date_time=datetime(2026, 10, 8, 12), description='Color')
        db.session.add(other)
        db.session.commit()
        path = f'/api/appointments/{self.turn.id}/reschedule'
        self.assertEqual(self.browser.post(path, json={'date_time': '2026-10-08T12:30'}).status_code, 409)
        self.assertEqual(self.turn.date_time.hour, 10)
        self.assertEqual(self.browser.post(path, json={'date_time': '2026-10-08T11:00'}).status_code, 200)
        db.session.expire_all()
        self.assertEqual(db.session.get(Appointment, self.turn.id).date_time.hour, 11)
        self.assertEqual(self.browser.post(path, json={'date_time': 'bad'}).status_code, 400)

    def test_add_and_edit_reject_conflicts(self):
        response = self.browser.post('/appointments/add', data={'client_id': self.client.id, 'date_time': '2026-10-08T10:30', 'description': 'Color'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.query.count(), 1)
        other = Appointment(client_id=self.client.id, date_time=datetime(2026, 10, 8, 12), description='Color')
        db.session.add(other)
        db.session.commit()
        self.browser.post(f'/clients/{self.client.id}/appointments/edit/{other.id}', data={'date_time': '2026-10-08T10:30', 'description': 'Color'})
        self.assertEqual(db.session.get(Appointment, other.id).date_time.hour, 12)

    def test_google_import_review_and_duplicate_prevention(self):
        event = {'id': 'google-1', 'summary': 'Eli weber', 'start': {'dateTime': '2026-10-09T17:00:00Z'}}
        with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.list_google_events', return_value=[event]), patch('app.routes.get_google_event', return_value=event):
            response = self.browser.get('/google-calendar/import?from_date=2026-10-01&to_date=2026-10-31')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Eli weber', response.data)
            self.assertIn(b'Ana Perez', response.data)
            data = {'from_date': '2026-10-01', 'to_date': '2026-10-31', 'event_id': 'google-1', 'client_google-1': str(self.client.id)}
            self.browser.post('/google-calendar/import', data=data)
            self.browser.post('/google-calendar/import', data=data)
            turn = Appointment.query.filter_by(google_event_id='google-1').one()
            self.assertEqual(turn.client_id, self.client.id)
            self.assertEqual(turn.date_time, datetime(2026, 10, 9, 14))
            self.assertEqual(Appointment.query.count(), 2)

    def test_google_import_all_day_requires_time_and_rejects_conflicts(self):
        event = {'id': 'day-1', 'summary': 'Color', 'start': {'date': '2026-10-08'}}
        with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.list_google_events', return_value=[event]), patch('app.routes.get_google_event', return_value=event):
            data = {'from_date': '2026-10-01', 'to_date': '2026-10-31', 'event_id': 'day-1', 'client_day-1': str(self.client.id)}
            self.browser.post('/google-calendar/import', data=data)
            self.assertEqual(Appointment.query.count(), 1)
            data['time_day-1'] = '10:30'
            self.browser.post('/google-calendar/import', data=data)
            self.assertEqual(Appointment.query.count(), 1)
            data['time_day-1'] = '12:00'
            self.browser.post('/google-calendar/import', data=data)
            self.assertEqual(Appointment.query.filter_by(google_event_id='day-1').one().date_time.hour, 12)

    def test_google_import_connection_and_invalid_selection(self):
        self.assertEqual(self.browser.get('/google-calendar/import').status_code, 302)
        with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.get_google_event') as fetch:
            self.browser.post('/google-calendar/import', data={'event_id': 'invalid', 'client_invalid': '999999'})
            fetch.assert_not_called()
            self.assertEqual(Appointment.query.count(), 1)


if __name__ == '__main__':
    unittest.main()
