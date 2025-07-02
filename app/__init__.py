from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

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

# Inicializa la extensión SQLAlchemy
db = SQLAlchemy(app)

# Importa las rutas para que la aplicación las conozca
from app import routes, models

# Asegúrate de que los modelos se carguen antes de crear la base de datos
with app.app_context():
    db.create_all()
