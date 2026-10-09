import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch
from tempfile import TemporaryDirectory

from app import app
from app.google_calendar_sync import renew_google_watch, google_watch_active, clear_google_watch

from app.google_calendar import google_event_start, list_google_events


class GoogleImportTests(unittest.TestCase):
    def test_timezone_and_all_day(self):
        with patch.dict('os.environ', {'GOOGLE_CALENDAR_TIMEZONE': 'America/Argentina/Buenos_Aires'}):
            self.assertEqual(google_event_start({'start': {'dateTime': '2026-10-09T02:00:00Z'}}), datetime(2026, 10, 8, 23))
            self.assertIsNone(google_event_start({'start': {'date': '2026-10-09'}}))
            self.assertEqual(google_event_start({'start': {'date': '2026-10-09'}}, '13:30'), datetime(2026, 10, 9, 13, 30))

    def test_pagination_and_cancelled_events(self):
        service = MagicMock()
        service.events.return_value.list.return_value.execute.side_effect = [
            {'items': [], 'nextPageToken': 'next'},
            {'items': [{'id': 'yes'}, {'id': 'no', 'status': 'cancelled'}]},
        ]
        with patch('app.google_calendar.calendar_service', return_value=service):
            events = list_google_events(date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(events, [{'id': 'yes'}])
        calls = service.events.return_value.list.call_args_list
        self.assertTrue(calls[0].kwargs['singleEvents'])
        self.assertEqual(calls[1].kwargs['pageToken'], 'next')
        self.assertTrue(calls[0].kwargs['timeMax'].startswith('2026-11-01T00:00:00'))

    def test_watch_registration_reuse_and_disconnect(self):
        service = MagicMock()
        service.events.return_value.watch.return_value.execute.return_value = {'resourceId': 'resource', 'expiration': '9999999999999'}
        with TemporaryDirectory() as directory, app.app_context(), patch.object(app, 'instance_path', directory), patch.dict('os.environ', {'GOOGLE_REDIRECT_URI': 'https://example.com/google-calendar/callback', 'GOOGLE_CALENDAR_ID': 'primary'}), patch('app.google_calendar_sync.google_calendar_connected', return_value=True), patch('app.google_calendar_sync.calendar_service', return_value=service):
            state = renew_google_watch()
            self.assertEqual(state['address'], 'https://example.com/google-calendar/notifications')
            self.assertTrue(google_watch_active())
            self.assertEqual(renew_google_watch()['id'], state['id'])
            service.events.return_value.watch.assert_called_once()
            clear_google_watch()
            self.assertFalse(google_watch_active())

    def test_watch_failure_restores_previous_channel(self):
        from app.google_calendar_sync import _read_state, _write_state
        service = MagicMock()
        service.events.return_value.watch.return_value.execute.side_effect = RuntimeError('offline')
        with TemporaryDirectory() as directory, app.app_context(), patch.object(app, 'instance_path', directory), patch.dict('os.environ', {'GOOGLE_REDIRECT_URI': 'https://example.com/google-calendar/callback'}), patch('app.google_calendar_sync.google_calendar_connected', return_value=True), patch('app.google_calendar_sync.calendar_service', return_value=service):
            old = {'id': 'previous', 'expiration': 1}
            _write_state('google_calendar_watch.json', old)
            with self.assertRaises(RuntimeError):
                renew_google_watch()
            self.assertEqual(_read_state('google_calendar_watch.json'), old)


if __name__ == '__main__':
    unittest.main()
