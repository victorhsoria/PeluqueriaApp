# Actualizar precios desde Excel

Productos > Actualizar precios desde Excel. Subir un archivo .xlsx (hasta 8 MB),
generar la vista previa, revisar las coincidencias y confirmar la actualizacion.
No se cambia ningun precio al subir el archivo ni al guardar la seleccion.

## Formatos

Se admite el archivo del proveedor ",listas distr 2026-05-04.xlsx": una hoja por
marca, encabezados COD BARRA / DESCRIPCION / COD PROV (o COD INT/TOTVS) / DISTR.
Tambien se admite ARTICULOS en lugar de DESCRIPCION y listas simples con Marca,
Descripcion y Precio mayorista. Un campo ID o ID producto se interpreta como
el identificador interno de la aplicacion, no como un codigo del proveedor.
El encabezado debe estar en las primeras 20 filas y columnas de cada hoja.

Se leen todas las hojas, ignorando titulos de seccion y filas vacias. Se usan
valores numericos o resultados ya calculados del Excel: no se ejecutan formulas.
Si un archivo tiene formulas sin resultados guardados, abrirlo en Excel o
LibreOffice, recalcular y guardar antes de subirlo. No se admite el formato .xls.
Limites: 120 hojas, 20.000 filas y 64 MB descomprimidos. La vista previa vence
al cabo de una hora; los borradores se guardan privados en instance/price_imports.

## Coincidencias y confirmacion

Se busca por ID interno, equivalencias ya confirmadas o marca y descripcion
normalizadas (mayusculas, acentos y espacios). No se usan coincidencias difusas.
Los productos sin coincidencia se vinculan manualmente mediante el selector.
Guardar seleccion o navegar con Anterior/Siguiente conserva las selecciones.
Cambiar filtros sin guardar puede perder los cambios de la pagina actual.
Si se cambian vinculos al confirmar, primero se guarda la seleccion y se vuelve
a la vista previa para revisar los importes correctos antes de confirmar otra vez.

La confirmacion aplica TODAS las filas seleccionadas de la vista previa, no solo
la pagina visible. Seleccionar "No importar" para omitir filas. No se permite
aplicar dos filas al mismo producto.
Los codigos repetidos no se recuerdan como equivalencias automaticas.

## Productos nuevos

En una fila sin coincidencia, elegir "Crear producto nuevo (stock 0)".
Revisar o ajustar marca y descripcion e ingresar el porcentaje de venta deseado
(0 es valido si se quiere vender al costo). Guardar seleccion muestra el precio
de venta calculado antes de confirmar. Tambien se puede filtrar por
"Nuevos seleccionados" o "Seleccionados" para revisar el lote mixto.

Solo se crean las filas seleccionadas expresamente. El stock inicial siempre
es cero, no se toman cantidades del Excel y no se carga automaticamente todo
el catalogo. Los existentes conservan su porcentaje y stock. Se recuerdan los
codigos unicos para que proximas listas actualicen el registro creado.

Se rechazan duplicados por marca/descripcion normalizadas o vinculo conocido,
tanto contra el inventario actual como entre nuevos del mismo lote. Las
descripciones diferentes de un mismo articulo deben vincularse manualmente a
su registro existente para evitar duplicados semanticos. Una fila con un ID
interno inexistente no puede crear un producto nuevo con ese ID.
Si hay un conflicto, se revierte todo el lote, incluidas las altas.

Se actualiza el precio mayorista y se recalcula el precio de venta con el
porcentaje actual del producto, redondeando a centavos. No se cambia el stock,
el porcentaje de venta, el nombre ni la marca. Los pedidos y trabajos anteriores
conservan sus importes. Los nuevos presupuestos tomaran el nuevo costo; los
existentes solo cambian si se actualizan y guardan expresamente.

Si un precio o porcentaje cambia entre la vista previa y la confirmacion, se
cancela el lote completo y se debe cargar el archivo nuevamente. Un cambio de
stock no cancela la importacion ni se sobrescribe. Revisar la fecha de cada hoja:
una lista antigua puede bajar precios que ya habian sido actualizados.

## PythonAnywhere

Hacer una copia de seguridad y aplicar dependencias/migracion antes de Reload:

```bash
cd ~/PeluqueriaApp
source venv/bin/activate
cp app/peluqueria.db "app/peluqueria-backup-$(date +%Y%m%d-%H%M%S).db"
git pull origin main
pip install -r requirements.txt
python -m flask --app run db upgrade
```

La migracion crea product_price_link para recordar equivalencias. No modifica
precios existentes. Despues, Web > Reload, subir la lista y revisar la vista previa.
