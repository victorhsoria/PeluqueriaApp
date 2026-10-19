# Costos de coloracion

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

Despues, Web > Reload. La migracion agrega una columna JSON opcional a service;
no cambia los precios ni los productos de trabajos anteriores. No omitir
la migracion: el nuevo modelo necesita esa columna.
