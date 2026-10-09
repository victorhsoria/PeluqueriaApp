import unittest
from tempfile import TemporaryDirectory
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
        self.instance_directory = TemporaryDirectory()
        self.instance_patch = patch.object(app, 'instance_path', self.instance_directory.name)
        self.instance_patch.start()

    def tearDown(self):
        self.instance_patch.stop()
        self.instance_directory.cleanup()
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

    def test_google_refresh_updates_linked_and_displays_new_without_duplicate(self):
        self.turn.google_event_id = 'linked'
        db.session.commit()
        events = [
            {'id': 'linked', 'summary': 'Ana Perez: Color', 'start': {'dateTime': '2026-10-09T14:00:00-03:00'}, 'end': {'dateTime': '2026-10-09T16:00:00-03:00'}},
            {'id': 'external', 'summary': 'Comprar productos', 'start': {'date': '2026-10-10'}, 'end': {'date': '2026-10-11'}},
        ]
        with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.list_google_events', return_value=events), patch('app.google_calendar_sync.calendar_service', return_value=object()):
            for _ in range(2):
                response = self.browser.post('/api/google-calendar/refresh', json={'start': '2026-10-05', 'end': '2026-10-12'})
                self.assertEqual(response.status_code, 200)
                result = response.get_json()['events']
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]['end'], '2026-10-09T16:00:00')
                self.assertTrue(result[1]['allDay'])
                self.assertFalse(result[1]['editable'])
                self.assertEqual(Appointment.query.count(), 1)
            self.assertEqual(self.turn.date_time, datetime(2026, 10, 9, 14))
            self.assertEqual(self.turn.description, 'Color')

    def test_google_background_cancellation_and_all_day_preserve_association(self):
        from app.google_calendar_sync import receive_google_changes
        self.turn.google_event_id = 'linked'
        db.session.commit()
        with patch('app.google_calendar_sync.calendar_service', return_value=object()), patch('app.google_calendar_sync.get_google_event', return_value={'status': 'cancelled'}):
            receive_google_changes([{'id': 'linked', 'summary': 'Color', 'start': {'date': '2026-10-10'}}])
            self.assertEqual(self.turn.date_time, datetime(2026, 10, 10, 10))
            self.assertEqual(self.turn.client_id, self.client.id)
            receive_google_changes([])
            self.assertEqual(Appointment.query.count(), 0)
            self.assertIsNotNone(db.session.get(Client, self.client.id))

    def test_google_failure_never_deletes_local_turns(self):
        self.turn.google_event_id = 'linked'
        db.session.commit()
        with patch('app.routes.google_calendar_connected', return_value=True), patch('app.routes.list_google_events', side_effect=RuntimeError('Network unavailable')):
            result = self.browser.post('/api/google-calendar/refresh', json={'start': '2026-10-05', 'end': '2026-10-12'}).get_json()
            self.assertIsNotNone(result['warning'])
            self.assertEqual(len(result['events']), 1)
            self.assertEqual(Appointment.query.count(), 1)
        self.assertEqual(self.browser.post('/api/google-calendar/refresh', json={'start': 'bad'}).status_code, 400)

    def test_google_read_failure_does_not_partially_update_turns(self):
        from app.google_calendar_sync import receive_google_changes
        self.turn.google_event_id = 'first'
        db.session.add(Appointment(client_id=self.client.id, date_time=datetime(2026, 10, 8, 12), description='Color', google_event_id='second'))
        db.session.commit()
        event = {'id': 'first', 'summary': 'Cambio', 'start': {'dateTime': '2026-10-09T14:00:00-03:00'}}
        with patch('app.google_calendar_sync.calendar_service', return_value=object()), patch('app.google_calendar_sync.get_google_event', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                receive_google_changes([event])
        self.assertEqual(self.turn.date_time, datetime(2026, 10, 8, 10))
        self.assertEqual(self.turn.description, 'Corte')

    def test_google_notification_security_and_closed_browser_sync(self):
        from app.google_calendar_sync import _write_state
        self.turn.google_event_id = 'linked'
        db.session.commit()
        _write_state('google_calendar_watch.json', {'id': 'channel', 'token': 'test-secret', 'resource_id': 'resource', 'calendar_id': 'primary', 'expiration': 9999999999999})
        headers = {'X-Goog-Channel-ID': 'channel', 'X-Goog-Channel-Token': 'test-secret', 'X-Goog-Resource-ID': 'resource', 'X-Goog-Resource-State': 'exists'}
        event = {'id': 'linked', 'summary': 'Nuevo horario', 'start': {'dateTime': '2026-10-12T15:00:00-03:00'}}
        with patch('app.google_calendar_sync.google_calendar_connected', return_value=True), patch('app.google_calendar_sync.calendar_service', return_value=object()), patch('app.google_calendar_sync.list_google_events', return_value=[event]):
            self.assertEqual(self.browser.post('/google-calendar/notifications').status_code, 403)
            self.assertEqual(self.browser.post('/google-calendar/notifications', headers={**headers, 'X-Goog-Channel-Token': 'wrong'}).status_code, 403)
            self.assertEqual(self.browser.post('/google-calendar/notifications', headers={**headers, 'X-Goog-Resource-ID': 'wrong'}).status_code, 403)
            self.assertEqual(self.browser.post('/google-calendar/notifications', headers=headers).status_code, 204)
            self.assertEqual(self.turn.date_time, datetime(2026, 10, 12, 15))
            self.assertEqual(self.turn.description, 'Nuevo horario')

    def test_google_notifications_return_retry_status_on_network_failure(self):
        with patch('app.routes.valid_google_notification', return_value=True), patch('app.routes.sync_google_background', side_effect=RuntimeError('offline')):
            self.assertEqual(self.browser.post('/google-calendar/notifications', headers={'X-Goog-Resource-State': 'sync'}).status_code, 204)
            self.assertEqual(self.browser.post('/google-calendar/notifications', headers={'X-Goog-Resource-State': 'exists'}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
