import json
import os
from datetime import timedelta

from flask import current_app


SCOPES = ['https://www.googleapis.com/auth/calendar.events']


def _token_path():
    os.makedirs(current_app.instance_path, exist_ok=True)
    return os.path.join(current_app.instance_path, 'google_calendar_token.json')


def _calendar_id():
    return os.environ.get('GOOGLE_CALENDAR_ID', 'primary')


def _timezone():
    return os.environ.get('GOOGLE_CALENDAR_TIMEZONE', 'America/Argentina/Buenos_Aires')


def _event_minutes():
    try:
        return int(os.environ.get('GOOGLE_CALENDAR_EVENT_MINUTES', '60'))
    except ValueError:
        return 60


def google_calendar_configured():
    return bool(os.environ.get('GOOGLE_CLIENT_ID') and os.environ.get('GOOGLE_CLIENT_SECRET'))


def google_calendar_connected():
    return os.path.exists(_token_path())


def delete_google_token():
    token_path = _token_path()
    if os.path.exists(token_path):
        os.remove(token_path)


def build_google_flow(redirect_uri):
    from google_auth_oauthlib.flow import Flow

    client_config = {
        'web': {
            'client_id': os.environ['GOOGLE_CLIENT_ID'],
            'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token',
            'redirect_uris': [redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    return flow


def save_credentials(credentials):
    with open(_token_path(), 'w', encoding='utf-8') as token_file:
        token_file.write(credentials.to_json())


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_path = _token_path()
    if not os.path.exists(token_path):
        return None

    with open(token_path, 'r', encoding='utf-8') as token_file:
        token_data = json.load(token_file)

    credentials = Credentials.from_authorized_user_info(token_data, SCOPES)
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(credentials)

    if not credentials.valid:
        return None

    return credentials


def calendar_service():
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    import httplib2

    credentials = get_credentials()
    if not credentials:
        return None

    # PythonAnywhere free accounts require HTTP CONNECT through their proxy.
    proxy_url = (
        os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')
        or os.environ.get('http_proxy') or os.environ.get('HTTP_PROXY')
    )
    proxy_info = httplib2.proxy_info_from_url(proxy_url) if proxy_url else None
    transport = httplib2.Http(proxy_info=proxy_info, timeout=30)
    authorized_http = AuthorizedHttp(credentials, http=transport)
    return build('calendar', 'v3', http=authorized_http, cache_discovery=False)


def appointment_to_google_event(appointment):
    start = appointment.date_time
    end = start + timedelta(minutes=_event_minutes())
    client_name = f'{appointment.client.first_name} {appointment.client.last_name}'

    return {
        'summary': f'{client_name}: {appointment.description}',
        'description': 'Turno registrado en Peluqueria App.',
        'start': {
            'dateTime': start.isoformat(),
            'timeZone': _timezone(),
        },
        'end': {
            'dateTime': end.isoformat(),
            'timeZone': _timezone(),
        },
    }


def sync_appointment_to_google(appointment):
    service = calendar_service()
    if not service:
        raise RuntimeError('La autorizacion de Google Calendar no es valida. Conecta la cuenta nuevamente.')

    event_body = appointment_to_google_event(appointment)
    events = service.events()
    if appointment.google_event_id:
        event = events.update(
            calendarId=_calendar_id(),
            eventId=appointment.google_event_id,
            body=event_body
        ).execute()
    else:
        event = events.insert(
            calendarId=_calendar_id(),
            body=event_body
        ).execute()

    return event.get('id')


def delete_appointment_from_google(google_event_id):
    service = calendar_service()
    if not service or not google_event_id:
        return

    service.events().delete(calendarId=_calendar_id(), eventId=google_event_id).execute()
