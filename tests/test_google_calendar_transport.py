import unittest
from unittest.mock import patch

import httplib2
import socks
from google.oauth2.credentials import Credentials

from app.google_calendar import calendar_service, sync_appointment_to_google


class GoogleCalendarTransportTests(unittest.TestCase):
    def build_service(self, environment):
        credentials = Credentials(token='test-token')
        with patch.dict('os.environ', environment, clear=True), \
                patch('app.google_calendar.get_credentials', return_value=credentials), \
                patch('googleapiclient.discovery.build') as build:
            calendar_service()
        build.assert_called_once()
        self.assertEqual(build.call_args.args, ('calendar', 'v3'))
        self.assertNotIn('credentials', build.call_args.kwargs)
        authorized_http = build.call_args.kwargs['http']
        self.assertIs(authorized_http.credentials, credentials)
        self.assertEqual(authorized_http.http.timeout, 30)
        return authorized_http.http

    def test_pythonanywhere_https_proxy(self):
        transport = self.build_service({'https_proxy': 'http://proxy.server:3128'})
        self.assertIsInstance(transport.proxy_info, httplib2.ProxyInfo)
        self.assertEqual(transport.proxy_info.proxy_host, 'proxy.server')
        self.assertEqual(transport.proxy_info.proxy_port, 3128)
        self.assertEqual(transport.proxy_info.proxy_type, socks.PROXY_TYPE_HTTP)

    def test_uppercase_proxy_and_https_precedence(self):
        transport = self.build_service({'HTTPS_PROXY': 'http://secure-proxy:8080', 'http_proxy': 'http://other-proxy:3128'})
        self.assertEqual(transport.proxy_info.proxy_host, 'secure-proxy')
        self.assertEqual(transport.proxy_info.proxy_port, 8080)

    def test_http_proxy_fallback(self):
        transport = self.build_service({'http_proxy': 'http://proxy.server:3128'})
        self.assertEqual(transport.proxy_info.proxy_host, 'proxy.server')

    def test_direct_connection_without_proxy(self):
        self.assertIsNone(self.build_service({}).proxy_info)

    def test_no_credentials_does_not_build_service(self):
        with patch('app.google_calendar.get_credentials', return_value=None), \
                patch('googleapiclient.discovery.build') as build:
            self.assertIsNone(calendar_service())
        build.assert_not_called()

    def test_missing_authorization_cannot_count_as_synced(self):
        with patch('app.google_calendar.calendar_service', return_value=None):
            with self.assertRaises(RuntimeError):
                sync_appointment_to_google(None)


if __name__ == '__main__':
    unittest.main()
