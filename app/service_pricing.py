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
    if kind not in ('raiz', 'completo', 'aplicacion') or length not in ('corto', 'melena', 'largo', 'extralargo', 'abundante', 'todos'):
        raise ValueError('Tipo de coloracion o largo invalido.')
    material_total = sum((Decimal(row['cost']) for row in materials), Decimal(0))
    total = Decimal(money(material_total + labour + overhead + other))
    template_id = data.get('template_id')
    if template_id is not None and (type(template_id) is not int or template_id <= 0):
        raise ValueError('Plantilla de servicio invalida.')
    result = {
        'version': 1, 'kind': kind, 'length': length, 'materials': materials,
        'labour': money(labour), 'overhead': money(overhead), 'other_costs': money(other),
        'margin': str(margin), 'material_total': money(material_total),
        'total_cost': money(total), 'suggested_price': money(total / (1 - margin / 100)),
    }
    if template_id is not None:
        result['template_id'] = template_id
    confirmed = data.get('costs_confirmed', True)
    if not isinstance(confirmed, bool):
        raise ValueError('Estado de costos invalido.')
    if not confirmed:
        result['costs_confirmed'] = False
    if data.get('reference_price') not in (None, ''):
        result['reference_price'] = money(amount(data['reference_price'], 'Precio de referencia'))
    example_key = data.get('example_key')
    if example_key is not None:
        if not isinstance(example_key, str) or len(example_key) > 80:
            raise ValueError('Referencia de ejemplo invalida.')
        result['example_key'] = example_key
    return result


def refresh_color_pricing(data, products, template=None):
    pricing = calculate_color_pricing(data)
    changes = []
    warnings = []
    for row in pricing['materials']:
        if row['product_id'] is None or row['client_supplied']:
            continue
        product = products.get(row['product_id'])
        if product is None:
            warnings.append(f"{row['label']}: producto no disponible; se conserva el costo guardado.")
            continue
        new_cost = money(amount(product.wholesale_price, 'Costo del producto'))
        if Decimal(row['package_cost']) != Decimal(new_cost):
            changes.append({'label': row['label'] + ' (envase)', 'before': money(Decimal(row['package_cost'])), 'after': new_cost, 'percent': False})
        row['package_cost'] = new_cost
    if template is not None:
        defaults = calculate_color_pricing(template.pricing)
        fields = [('labour', 'Mano de obra'), ('overhead', 'Gastos del salon'), ('other_costs', 'Otros costos'), ('margin', 'Margen sobre venta')] if defaults.get('costs_confirmed', True) else []
        if not defaults.get('costs_confirmed', True):
            warnings.append('Plantilla sin costos verificados; se conservan los costos del trabajo.')
        for key, label in fields:
            if Decimal(pricing[key]) != Decimal(defaults[key]):
                changes.append({'label': label, 'before': pricing[key], 'after': defaults[key], 'percent': key == 'margin'})
            pricing[key] = defaults[key]
        if 'reference_price' in defaults:
            if pricing.get('reference_price') != defaults['reference_price']:
                changes.append({'label': 'Precio de referencia', 'before': pricing.get('reference_price'), 'after': defaults['reference_price'], 'percent': False})
            pricing['reference_price'] = defaults['reference_price']
    elif pricing.get('template_id') is not None:
        warnings.append('La plantilla original ya no existe; se conservan mano de obra, gastos y margen.')
    return calculate_color_pricing(pricing), changes, warnings
