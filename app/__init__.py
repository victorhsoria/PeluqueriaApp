from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
import locale

# Inicializa la aplicación Flask
app = Flask(__name__)

# Configura una SECRET_KEY. ¡IMPORTANTE!
# En un entorno de producción, esta clave debe ser una cadena aleatoria
# muy larga y compleja, y debe mantenerse en secreto (ej. a través de variables de entorno).
app.config['SECRET_KEY'] = 'una_clave_secreta_super_segura_y_aleatoria_para_tu_app' # ¡Cámbiala por una más segura en producción!


# Configura la base de datos SQLite
# Utiliza una ruta absoluta para la base de datos para evitar problemas de ubicación
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'peluqueria.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurar la configuración regional a español de Argentina para el formato de fechas y moneda
try:
    locale.setlocale(locale.LC_ALL, 'es_AR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'es_AR')
    except locale.Error:
        print("Advertencia: No se pudo establecer la configuración regional en español de Argentina. Las fechas y monedas podrían no mostrarse correctamente.")
        pass

# --- Filtro Jinja para formato de moneda ---
def format_currency(value):
    """Filtro para formatear un número como moneda en formato español."""
    if value is None:
        return locale.currency(0.0, symbol=True, grouping=True)
    return locale.currency(value, symbol=True, grouping=True)

# Registrar el filtro en el entorno de Jinja2
app.jinja_env.filters['currency'] = format_currency

# Inicializa la extensión SQLAlchemy
db = SQLAlchemy(app)
# Inicializa Flask-Migrate
migrate = Migrate(app, db)

# Importa las rutas para que la aplicación las conozca
from app import routes, models
