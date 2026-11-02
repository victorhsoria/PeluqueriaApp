# Costos de coloracion

## Ejemplos de precios de venta

Servicios > Cargar ejemplos Bucles agrega seis plantillas de referencia de color:
corto 39999, melena 44999, largo 49999, extralargo 54999,
extralargo abundante 59999 y solo aplicacion 19999 (pesos argentinos).
Fuente: https://www.bucles.com.ar/servicios/
Son datos del indice del buscador consultado el 2026-11-02; la lectura directa
del sitio fallo y NO se confirmo su vigencia. No se actualizan desde Internet.
Las plantillas se pueden editar y la carga repetida no reemplaza las existentes.

Esos importes son precios de venta de referencia, no costos de productos ni de
mano de obra. Los ejemplos no inventan formulas, cantidades ni margenes.
Se crean con "Costos verificados" desmarcado; no se muestran ganancias ni un
precio calculado hasta que el usuario ingrese y verifique sus propios costos.
"Usar precio de referencia" copia el importe al precio a cobrar, por separado
de "Usar precio sugerido". Ambos requieren una accion explicita del usuario.
El precio de referencia queda guardado junto al trabajo, sin modificar su costo.
La actualizacion de precios no reemplaza los costos reales por los ceros de una
plantilla de ejemplo que todavia no tenga costos verificados.

## Plantillas de servicios

En Servicios > Nueva plantilla, configurar un nombre (por ejemplo, "Raiz melena"),
tipo de trabajo, largo, productos, cantidades, mano de obra, gastos y margen.
Cada plantilla se puede editar o eliminar sin cambiar los trabajos anteriores.
Se puede crear una plantilla para cada combinacion de servicio y largo.

En un trabajo, seleccionar una plantilla y pulsar "Aplicar plantilla".
Se toman sus valores y el costo mayorista vigente de los productos vinculados.
No se modifica el precio a cobrar; se utiliza "Usar precio sugerido" si corresponde.

"Actualizar con precios actuales" consulta nuevamente el inventario y, si existe
la plantilla original, sus valores actuales de mano de obra, gastos y margen.
Conserva las cantidades, el largo, la descripcion y los insumos personalizados.
Muestra los importes anteriores y nuevos antes de aplicar. Cancelar no cambia
el presupuesto. Confirmar actualiza solo el formulario: hay que guardar el trabajo
para persistir los cambios. El importe cobrado nunca se reemplaza automaticamente.
Si falta un producto o una plantilla, se informa y se conservan sus valores previos.

En Clientes > Historial > Agregar trabajo (o Editar), activar
"Calcular costos de coloracion".

El costo por insumo es costo del envase / contenido del envase * consumo.
Contenido y consumo deben expresarse en la misma unidad: g, ml o unidad.
Se pueden agregar tinturas, oxidantes y descartables. Si el cliente aporta un
insumo, su costo para el salon es cero; los demas costos se conservan.

El costo total suma insumos, mano de obra, gastos del salon y otros costos.
El precio sugerido se calcula como costo total / (1 - margen / 100).
El margen es sobre la venta, no un recargo sobre el costo. No hay un margen
predeterminado ni una tarifa basada en otra peluqueria. Los impuestos y
comisiones que correspondan deben contemplarse en los costos ingresados.

"Usar precio sugerido" copia la sugerencia al precio a cobrar. Se puede cobrar
otro importe; ese es el ingreso registrado en los reportes. El servidor
recalcula y guarda el desglose, sin confiar en totales enviados por el navegador.
Los precios de referencia son los costos mayoristas del inventario. Los valores
guardados en un trabajo no cambian cuando se modifica un producto.

El consumo para presupuesto no descuenta stock fraccionado. El inventario
actual cuenta envases completos; solo se descuenta lo seleccionado en
"Descuento de inventario (envases completos)". No registrar un mismo consumo
dos veces ni descontar un envase completo por una aplicacion parcial.

## Actualizacion en PythonAnywhere

Hacer una copia de la base de datos antes de aplicar la migracion.
Desde la consola Bash del proyecto:

```bash
cd ~/PeluqueriaApp
source venv/bin/activate
cp app/peluqueria.db "app/peluqueria-backup-$(date +%Y%m%d-%H%M%S).db"
git pull origin main
python -m flask --app run db upgrade
```

Despues, Web > Reload. Las migraciones agregan el desglose JSON opcional a
service y la tabla service_template. No cambian los precios ni los productos
de trabajos anteriores. No omitir la migracion: los nuevos modelos necesitan
esas estructuras.
