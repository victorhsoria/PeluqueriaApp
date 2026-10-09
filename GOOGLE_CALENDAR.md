# Sincronizacion automatica en PythonAnywhere

La agenda consulta Google al abrirse y cada minuto mientras esta visible.
Las notificaciones HTTPS actualizan los turnos vinculados aunque el navegador
este cerrado. Los eventos nuevos se guardan en una cache privada y se muestran
en la agenda sin tener que importarlos. Para incluirlos en el historial de un
cliente, se vinculan una sola vez desde "Vincular clientes". No se deduce un
cliente a partir de apodos, ni se convierten compras o recordatorios en turnos.

Google es la fuente de verdad para la fecha y titulo de los turnos vinculados.
Una eliminacion en Google elimina el turno vinculado, no el cliente ni sus trabajos.
Los eventos sin horario conservan en el historial la hora asignada al vincularlos;
en el calendario se muestran como eventos de dia completo.

## Instalacion

1. Actualizar el codigo y las dependencias, y recargar la aplicacion en Web.
2. Conservar GOOGLE_REDIRECT_URI en el WSGI, antes de importar app:
   `https://victor398.pythonanywhere.com/google-calendar/callback`.
   La URL para notificaciones se calcula automaticamente. Si se necesita otra,
   configurar GOOGLE_WEBHOOK_URI con la URL HTTPS publica del endpoint
   `/google-calendar/notifications`. No es una URI de redireccion de OAuth.
3. En Calendario, pulsar "Activar sincronizacion automatica" una sola vez.
4. Crear una tarea diaria en PythonAnywhere, pestana Tasks, con este comando:

```bash
/home/victor398/PeluqueriaApp/venv/bin/python /home/victor398/PeluqueriaApp/sync_google_calendar.py --wsgi /var/www/victor398_pythonanywhere_com_wsgi.py
```

La tarea renueva los canales antes de que caduquen y recupera cambios por si se
perdio alguna notificacion. Google no garantiza entrega instantanea de cada
notificacion. Si la cuenta no permite tareas programadas, se necesita un plan
que las admita o un programador externo seguro; sin renovacion, el canal caduca.

Tokens, canales y cache se guardan en instance/, excluido de Git. No publicar
esta carpeta ni configurarla como archivos estaticos. No hay migracion de base
de datos para esta funcionalidad. Al desconectar se invalida el canal local.

Si el consentimiento OAuth sigue en modo "Testing", el permiso de renovacion
para Calendar caduca a los siete dias. Para un uso continuo, revisar el paso a
produccion en Google Auth Platform y los requisitos de verificacion que Google
indique, y volver a conectar la cuenta despues del cambio. La renovacion del
canal no extiende la vigencia del permiso OAuth.

## Prueba remota

Cambiar el horario de un turno vinculado en Google con el navegador de la
aplicacion cerrado. Luego abrir el historial del cliente y verificar el nuevo
horario. Crear tambien un evento no vinculado y verificar que aparece en la
agenda; un evento de dia completo debe aparecer en la banda "Todo el dia".

Referencias:
- https://developers.google.com/workspace/calendar/api/guides/push
- https://help.pythonanywhere.com/pages/ScheduledTasks/
- https://developers.google.com/identity/protocols/oauth2#expiration
