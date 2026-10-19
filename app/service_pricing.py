from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal('0.01')


def amount(value, label, positive=False):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label}: ingresa un numero valido.') from None
    if not result.is_finite() or result < 0 or result > Decimal('1000000000') or (positive and result < Decimal('0.001')):
        raise ValueError(f'{label}: valor fuera de rango.')
    return result


def money(value):
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def calculate_color_pricing(data):
    if not isinstance(data, dict):
        raise ValueError('El calculo de coloracion no es valido.')
    rows = data.get('materials', [])
    if not isinstance(rows, list) or len(rows) > 50:
        raise ValueError('Selecciona hasta 50 insumos.')
    materials = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Insumo invalido.')
        label = row.get('label', '')
        if not isinstance(label, str) or not label.strip() or len(label) > 255:
            raise ValueError('Completa el nombre de cada insumo (hasta 255 caracteres).')
        unit = row.get('unit', 'g')
        if unit not in ('g', 'ml', 'unidad'):
            raise ValueError('Unidad de consumo invalida.')
        package_cost = amount(row.get('package_cost', 0), 'Costo del envase')
        package_quantity = amount(row.get('package_quantity'), 'Contenido del envase', positive=True)
        quantity = amount(row.get('quantity'), 'Cantidad utilizada', positive=True)
        supplied = row.get('client_supplied', False)
        if not isinstance(supplied, bool):
            raise ValueError('Origen del producto invalido.')
        cost = Decimal(0) if supplied else package_cost * quantity / package_quantity
        product_id = row.get('product_id')
        if product_id is not None and (type(product_id) is not int or product_id <= 0):
            raise ValueError('Referencia de producto invalida.')
        materials.append({
            'label': label.strip(), 'unit': unit, 'package_cost': str(package_cost),
            'package_quantity': str(package_quantity), 'quantity': str(quantity),
            'client_supplied': supplied, 'cost': money(cost), 'product_id': product_id,
        })
    labour = Decimal(money(amount(data.get('labour', 0), 'Mano de obra')))
    overhead = Decimal(money(amount(data.get('overhead', 0), 'Gastos del salon')))
    other = Decimal(money(amount(data.get('other_costs', 0), 'Otros costos')))
    margin = amount(data.get('margin', 0), 'Margen')
    if margin >= 100:
        raise ValueError('El margen debe ser menor al 100%.')
    kind = data.get('kind', 'raiz')
    length = data.get('length', 'corto')
    if kind not in ('raiz', 'completo', 'aplicacion') or length not in ('corto', 'melena', 'largo', 'extralargo', 'abundante'):
        raise ValueError('Tipo de coloracion o largo invalido.')
    material_total = sum((Decimal(row['cost']) for row in materials), Decimal(0))
    total = Decimal(money(material_total + labour + overhead + other))
    return {
        'version': 1, 'kind': kind, 'length': length, 'materials': materials,
        'labour': money(labour), 'overhead': money(overhead), 'other_costs': money(other),
        'margin': str(margin), 'material_total': money(material_total),
        'total_cost': money(total), 'suggested_price': money(total / (1 - margin / 100)),
    }
