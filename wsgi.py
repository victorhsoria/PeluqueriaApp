import sys
import os

# Agrega la ruta de tu proyecto al path de Python.
# Esto asegura que Python pueda encontrar tu módulo 'app'.
# La ruta puede variar ligeramente dependiendo de cómo configures tu web app en PythonAnywhere.
# Por defecto, PythonAnywhere espera que tu código esté en /home/tu_usuario/tu_repo_github
project_home = u'/home/tu_usuario/peluqueria_app' # ¡CAMBIA 'tu_usuario' por tu nombre de usuario de PythonAnywhere!
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Importa tu aplicación Flask desde tu paquete 'app'
# Asegúrate de que 'app' en `from app import app` se refiere a la instancia de Flask
from app import app as application # Renombramos 'app' a 'application' para cumplir con el estándar WSGI

# En PythonAnywhere, Flask ya estará en el entorno virtual,
# así que no necesitas importar directamente Flask aquí a menos que quieras algo específico.
# El servidor web llamará a la instancia 'application'.

# NOTA: En un entorno de producción, es una buena práctica deshabilitar el modo de depuración (debug=True)
# Esto ya está manejado por PythonAnywhere al correr en producción.
