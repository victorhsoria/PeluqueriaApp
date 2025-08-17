from app import app, db
import os
from datetime import datetime, UTC # Importa UTC aquí



# Context processor para hacer el año actual disponible en todas las plantillas
@app.context_processor
def inject_current_year():
    # Usar datetime.now(datetime.UTC) para obtener la fecha y hora actual en UTC
    return {'current_year': datetime.now(UTC).year}

if __name__ == '__main__':
    # Ejecuta la aplicación en modo depuración (útil para desarrollo)
    app.run(debug=True)
