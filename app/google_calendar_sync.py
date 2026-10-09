import hmac
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from flask import current_app

from app import db
from app.models import Appointment
from app.google_calendar import (
    _calendar_id, _timezone, calendar_service, get_google_event,
    google_calendar_connected, google_event_start, list_google_events,
)


def _read_state(name):
    path = Path(current_app.instance_path) / name
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        current_app.logger.warning('No se pudo leer el estado local de Google Calendar.')
        return {}


def _write_state(name, state):
    path = Path(current_app.instance_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{name}.{uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(state), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def webhook_url():
    explicit = os.environ.get('GOOGLE_WEBHOOK_URI')
    redirect = os.environ.get('GOOGLE_REDIRECT_URI', '')
    url = explicit or (redirect.rsplit('/google-calendar/', 1)[0] + '/google-calendar/notifications' if '/google-calendar/' in redirect else '')
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.netloc:
        raise ValueError('Configura GOOGLE_REDIRECT_URI o GOOGLE_WEBHOOK_URI con una URL HTTPS publica.')
    return url


def renew_google_watch():
    if not google_calendar_connected():
        raise RuntimeError('Primero conecta Google Calendar.')
    old = _read_state('google_calendar_watch.json')
    now = int(datetime.now().timestamp() * 1000)
    if old.get('calendar_id') == _calendar_id() and old.get('address') == webhook_url() and int(old.get('expiration', 0)) > now + 2 * 86400000:
        return old
    service = calendar_service()
    if not service:
        raise RuntimeError('Conecta Google Calendar nuevamente.')
    channel = {
        'id': uuid4().hex, 'token': secrets.token_urlsafe(32),
        'address': webhook_url(), 'calendar_id': _calendar_id(),
        'expiration': now + 7 * 86400000,
    }
    # Register before watch: Google's initial notification can arrive before its response.
    _write_state('google_calendar_watch.json', channel)
    try:
        result = service.events().watch(calendarId=_calendar_id(), body={
            'id': channel['id'], 'token': channel['token'], 'type': 'web_hook',
            'address': channel['address'], 'expiration': str(channel['expiration']),
        }).execute()
        channel['resource_id'] = result['resourceId']
        channel['expiration'] = int(result['expiration'])
        _write_state('google_calendar_watch.json', channel)
    except Exception:
        _write_state('google_calendar_watch.json', old)
        raise
    if old.get('resource_id'):
        try:
            service.channels().stop(body={'id': old['id'], 'resourceId': old['resource_id']}).execute()
        except Exception:
            current_app.logger.warning('No se pudo detener el canal anterior de Google Calendar.')
    return channel


def google_watch_active():
    state = _read_state('google_calendar_watch.json')
    return bool(state.get('resource_id') and state.get('calendar_id') == _calendar_id()
                and int(state.get('expiration', 0)) > datetime.now().timestamp() * 1000)


def valid_google_notification(headers):
    state = _read_state('google_calendar_watch.json')
    if not state or state.get('calendar_id') != _calendar_id() or not google_calendar_connected():
        return False
    if int(state.get('expiration', 0)) <= datetime.now().timestamp() * 1000:
        return False
    if not hmac.compare_digest(headers.get('X-Goog-Channel-ID', '').encode(), state.get('id', '').encode()):
        return False
    if not hmac.compare_digest(headers.get('X-Goog-Channel-Token', '').encode(), state.get('token', '').encode()):
        return False
    resource = headers.get('X-Goog-Resource-ID', '')
    if state.get('resource_id'):
        return hmac.compare_digest(resource.encode(), state['resource_id'].encode())
    return bool(resource and headers.get('X-Goog-Resource-State') == 'sync')


def clear_google_watch():
    (Path(current_app.instance_path) / 'google_calendar_watch.json').unlink(missing_ok=True)
    (Path(current_app.instance_path) / 'google_calendar_cache.json').unlink(missing_ok=True)


def receive_google_changes(events=None, service=None):
    service = service or calendar_service()
    if not service:
        raise RuntimeError('Conecta Google Calendar nuevamente.')
    if events is None:
        today = datetime.now(ZoneInfo(_timezone())).date()
        events = list_google_events(today - timedelta(days=365), today + timedelta(days=366), service)
    by_id = {event['id']: event for event in events}
    changes = []
    # Read every remote event before changing the database; a network failure must not partially delete turns.
    for appointment in Appointment.query.filter(Appointment.google_event_id.isnot(None)).all():
        event = by_id.get(appointment.google_event_id)
        if event is None:
            try:
                event = get_google_event(appointment.google_event_id, service)
            except Exception as error:
                if getattr(getattr(error, 'resp', None), 'status', None) not in (404, 410):
                    raise
                event = {'status': 'cancelled'}
        if event.get('status') == 'cancelled':
            changes.append((appointment, None, None))
            continue
        start = google_event_start(event, appointment.date_time.strftime('%H:%M'))
        summary = event.get('summary') or 'Turno de Google Calendar'
        prefix = f'{appointment.client.first_name} {appointment.client.last_name}: '
        description = summary[len(prefix):] if summary.startswith(prefix) else summary
        changes.append((appointment, start, description[:255]))
    try:
        for appointment, start, description in changes:
            if start is None:
                db.session.delete(appointment)
            else:
                appointment.date_time = start
                appointment.description = description
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return events


def sync_google_background():
    events = receive_google_changes()
    _write_state('google_calendar_cache.json', {'calendar_id': _calendar_id(), 'events': events})
    return len(events)


def cached_google_events():
    cache = _read_state('google_calendar_cache.json')
    return cache.get('events', []) if cache.get('calendar_id') == _calendar_id() else []


def google_event_to_calendar(event):
    start = google_event_start(event)
    if start is None:
        day = event['start']['date']
        end = event.get('end', {}).get('date')
    else:
        day = start.isoformat()
        end_data = event.get('end', {})
        end = google_event_start({'start': end_data}).isoformat() if end_data.get('dateTime') else None
    link = event.get('htmlLink', '')
    parsed = urlparse(link)
    if parsed.scheme != 'https' or parsed.hostname not in ('www.google.com', 'calendar.google.com'):
        link = 'https://calendar.google.com/'
    return {
        'id': 'google:' + event['id'], 'google_event_id': event['id'],
        'title': event.get('summary') or 'Sin titulo', 'start': day, 'end': end,
        'allDay': start is None, 'date': day[:10], 'time': start.strftime('%H:%M') if start else '',
        'client_name': event.get('summary') or 'Sin titulo', 'description': 'Google Calendar',
        'url': link, 'source': 'google', 'editable': False, 'color': '#526b78',
    }
