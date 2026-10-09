import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

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


if __name__ == '__main__':
    unittest.main()
