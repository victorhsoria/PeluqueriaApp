import argparse
import runpy


def main():
    parser = argparse.ArgumentParser(description='Renovar notificaciones y sincronizar Google Calendar.')
    parser.add_argument('--wsgi', help='Archivo WSGI que define las variables de entorno de PythonAnywhere.')
    args = parser.parse_args()
    if args.wsgi:
        runpy.run_path(args.wsgi)
    from app import app
    from app.google_calendar_sync import renew_google_watch, sync_google_background
    with app.app_context():
        renew_google_watch()
        count = sync_google_background()
        print(f'Notificaciones activas. Se consultaron {count} eventos de Google Calendar.')


if __name__ == '__main__':
    main()
