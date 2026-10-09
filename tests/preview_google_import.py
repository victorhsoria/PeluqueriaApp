from datetime import date
from pathlib import Path
from tempfile import gettempdir
from types import SimpleNamespace

from flask import render_template
from app import app


with app.test_request_context('/google-calendar/import'):
    html = render_template(
        'google_calendar_import.html', title='Importar desde Google',
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 31),
        clients=[SimpleNamespace(id=1, first_name='Elizabeth', last_name='Weber')],
        linked={'linked'}, events=[
            {'id': 'timed', 'summary': 'Eli weber', 'date': '09/10/2026', 'time': '14:00'},
            {'id': 'day', 'summary': 'Color y corte', 'date': '10/10/2026', 'time': None},
            {'id': 'linked', 'summary': 'Turno registrado', 'date': '12/10/2026', 'time': '11:00'},
        ],
    )
    css = (Path(app.static_folder) / 'css' / 'styles.css').read_text(encoding='utf-8')
    html = html.replace('</head>', f'<style>{css}</style></head>')
    target = Path(gettempdir()) / 'peluqueria-google-import.html'
    target.write_text(html, encoding='utf-8')
    print(target)
