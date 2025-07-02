from app import app, db
import os
from datetime import datetime, UTC # Importa UTC aquí

# Asegúrate de que la base de datos se cree al iniciar la aplicación
# Si el archivo de la base de datos no existe, se creará
if not os.path.exists(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'peluqueria.db')):
    with app.app_context():
        db.create_all()
        print("Base de datos creada: peluqueria.db")

# Context processor para hacer el año actual disponible en todas las plantillas
@app.context_processor
def inject_current_year():
    # Usar datetime.now(datetime.UTC) para obtener la fecha y hora actual en UTC
    return {'current_year': datetime.now(UTC).year}

if __name__ == '__main__':
    # Ejecuta la aplicación en modo depuración (útil para desarrollo)
    app.run(debug=True)
