import hashlib
import json
import re
import secrets
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from flask import current_app
from sqlalchemy import update

from app import db
from app.models import Product, ProductPriceLink

MAX_UPLOAD = 8 * 1024 * 1024
MAX_ROWS = 20000
DRAFT_TTL = 3600


def normalize(value, brand=False):
    value = ''.join(char for char in unicodedata.normalize('NFKD', str(value or '')).casefold() if not unicodedata.combining(char))
    value = value.replace('\u00d7', 'x')
    return ''.join(char for char in value if char.isalnum() or (not brand and not char.isspace()))


def parse_price(value):
    if isinstance(value, (bool, date, datetime)) or value is None:
        raise ValueError('Precio no numerico o sin resultado calculado.')
    if isinstance(value, str):
        value = value.upper().replace('ARS', '').replace('$', '').replace('\u00a0', '').replace(' ', '')
        if ',' in value:
            value = value.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'\d{1,3}(\.\d{3})+', value):
            value = value.replace('.', '')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Precio no numerico.') from None
    if not number.is_finite() or not 0 < number <= 1000000000:
        raise ValueError('El precio debe ser positivo y no superar 1.000.000.000.')
    result = number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if not result:
        raise ValueError('El precio redondeado no puede ser cero.')
    return str(result)


def _code(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_price_workbook(content):
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError('Selecciona un archivo .xlsx de hasta 8 MB.')
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 5000 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
                raise ValueError('El contenido descomprimido del Excel es demasiado grande.')
        from openpyxl import load_workbook
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
    except (BadZipFile, KeyError, OSError) as error:
        raise ValueError('No se pudo leer el archivo .xlsx.') from error
    rows, warnings, sheets = [], [], []
    scanned = 0
    try:
        if len(workbook.worksheets) > 120:
            raise ValueError('El archivo supera el limite de 120 hojas.')
        for sheet in workbook:
            header = None
            brand_title = ''
            list_date = ''
            for number, values in enumerate(sheet.iter_rows(max_col=20, values_only=True), 1):
                scanned += 1
                if scanned > MAX_ROWS:
                    raise ValueError('El archivo supera el limite de 20.000 filas.')
                if number == 1:
                    brand_title = str(values[1] or '').strip()
                    list_date = next((value.date().isoformat() if isinstance(value, datetime) else value.isoformat() for value in values if isinstance(value, date)), '')
                normalized = {normalize(value, True): index for index, value in enumerate(values) if value is not None}
                if header is None:
                    price_col = next((normalized[key] for key in ('preciomayorista', 'costomayorista', 'distr', 'costo', 'precio') if key in normalized), None)
                    desc_col = next((normalized[key] for key in ('descripcion', 'articulos', 'producto', 'description') if key in normalized), None)
                    id_col = next((normalized[key] for key in ('id', 'idproducto') if key in normalized), None)
                    if price_col is not None and (desc_col is not None or id_col is not None):
                        header = {'price': price_col, 'description': desc_col, 'id': id_col,
                                  'brand': normalized.get('marca'),
                                  'barcode': next((normalized[key] for key in ('codbarra', 'codigoean', 'codean', 'codigodebarras', 'barcode') if key in normalized), None),
                                  'supplier': next((normalized[key] for key in ('codprov', 'codint', 'codtotvs') if key in normalized), None)}
                        if number == 1:
                            brand_title = ''
                        sheets.append(sheet.title)
                    elif number >= 20:
                        break
                    continue
                cell = lambda key: values[header[key]] if header[key] is not None else None
                description = str(cell('description') or '').strip()
                identifier = cell('id')
                barcode, supplier = _code(cell('barcode')), _code(cell('supplier'))
                price_value = cell('price')
                if not description and identifier is None:
                    continue
                if price_value is None and not barcode and not supplier and identifier is None:
                    continue  # Section headings are not products.
                brand = str(cell('brand') or brand_title or re.sub(r'\s+\d{4}-\d{2}.*$', '', sheet.title)).strip()
                try:
                    price = parse_price(price_value)
                    product_id = None
                    if identifier is not None:
                        product_id = int(str(identifier))
                        if product_id <= 0 or product_id > 9223372036854775807:
                            raise ValueError('ID de producto invalido.')
                except (ValueError, TypeError) as error:
                    if len(warnings) < 100:
                        warnings.append(f'{sheet.title}, fila {number}: {error}')
                    continue
                identity = 'internal:' + str(product_id) if product_id is not None else ('barcode:' + barcode if barcode else ('supplier:' + supplier if supplier else 'description:' + normalize(description)))
                key = hashlib.sha256((normalize(brand, True) + '\0' + identity).encode()).hexdigest()
                rows.append({'index': len(rows), 'sheet': sheet.title, 'row': number, 'brand': brand[:200],
                             'description': description[:500], 'barcode': barcode[:100], 'price': price,
                             'list_date': list_date, 'source_key': key, 'explicit_id': product_id})
            if header is None and len(warnings) < 100:
                warnings.append(f'{sheet.title}: no se encontraron columnas de producto y precio mayorista/DISTR.')
    finally:
        workbook.close()
    if not rows:
        raise ValueError('No se encontraron productos con precios validos en el Excel.')
    return {'rows': rows, 'warnings': warnings, 'sheets': sheets}


def product_signature(product):
    return {'brand': product.brand, 'description': product.description,
            'wholesale_price': str(product.wholesale_price), 'sale_percentage': str(product.sale_percentage)}


def sale_price(wholesale, percentage):
    percentage = Decimal(str(percentage))
    if not percentage.is_finite() or percentage < 0 or percentage > 1000000:
        raise ValueError('Un producto tiene un porcentaje de venta invalido.')
    return (Decimal(wholesale) * (1 + percentage / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def match_prices(parsed):
    products = Product.query.order_by(Product.brand, Product.description).all()
    by_id = {product.id: product for product in products}
    links = {link.source_key: link.product_id for link in ProductPriceLink.query.all()}
    by_description = defaultdict(list)
    for product in products:
        by_description[normalize(product.description)].append(product)
    counts = Counter(row['source_key'] for row in parsed['rows'])
    for row in parsed['rows']:
        target = None
        reason = 'Sin coincidencia'
        if row['explicit_id'] is not None:
            target = by_id.get(row['explicit_id'])
            reason = 'ID del producto' if target else 'ID inexistente'
        elif row['source_key'] in links and counts[row['source_key']] == 1:
            target = by_id.get(links[row['source_key']])
            reason = 'Vinculo guardado' if target else reason
        if target is None and row['explicit_id'] is None:
            brand_options = {normalize(part, True) for part in re.split(r'[/|]', row['brand'])}
            candidates = [product for product in by_description[normalize(row['description'])]
                          if normalize(product.brand, True) and normalize(product.brand, True) in brand_options]
            if len(candidates) == 1:
                target, reason = candidates[0], 'Marca y descripcion'
            elif len(candidates) > 1:
                reason = 'Coincidencia ambigua'
        row.update(product_id=target.id if target else None,
                   expected=product_signature(target) if target else None,
                   reason=reason, remember=counts[row['source_key']] == 1)
    return parsed


def save_draft(draft, token=None):
    folder = Path(current_app.instance_path) / 'price_imports'
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.glob('*.json'):
        if time.time() - path.stat().st_mtime > DRAFT_TTL * 2:
            path.unlink(missing_ok=True)
    token = token or secrets.token_hex(24)
    if not re.fullmatch('[a-f0-9]{48}', token):
        raise ValueError('Vista previa invalida.')
    path = folder / (token + '.json')
    temp = folder / (secrets.token_hex(24) + '.tmp')
    try:
        temp.write_text(json.dumps(draft), encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return token


def load_draft(token):
    if not isinstance(token, str) or not re.fullmatch('[a-f0-9]{48}', token):
        raise ValueError('Carga un Excel para generar la vista previa.')
    path = Path(current_app.instance_path) / 'price_imports' / (token + '.json')
    try:
        draft = json.loads(path.read_text(encoding='utf-8'))
        if time.time() - draft['created'] > DRAFT_TTL:
            raise ValueError('La vista previa vencio. Carga el Excel nuevamente.')
        return draft
    except (OSError, KeyError, json.JSONDecodeError):
        raise ValueError('La vista previa ya no esta disponible.') from None


def apply_prices(draft):
    selected = [row for row in draft['rows'] if row.get('product_id')]
    if not selected:
        raise ValueError('Selecciona al menos un producto para actualizar.')
    ids = [row['product_id'] for row in selected]
    if len(ids) != len(set(ids)):
        raise ValueError('Hay varias filas vinculadas al mismo producto. Conserva solo una seleccion por producto.')
    try:
        for row in selected:
            product = db.session.get(Product, row['product_id'])
            expected = row['expected']
            if product is None or product_signature(product) != expected:
                raise ValueError('Un producto cambio desde la vista previa. Carga nuevamente el Excel antes de aplicar.')
            wholesale = Decimal(parse_price(row['price']))
            sale = sale_price(wholesale, product.sale_percentage)
            result = db.session.execute(update(Product).where(
                Product.id == product.id, Product.wholesale_price == float(expected['wholesale_price']),
                Product.sale_percentage == float(expected['sale_percentage']),
                Product.brand == expected['brand'], Product.description == expected['description'],
            ).values(wholesale_price=float(wholesale), total_sale_price=float(sale)), execution_options={'synchronize_session': False})
            if result.rowcount != 1:
                raise ValueError('El producto cambio durante la actualizacion. No se aplicaron los precios.')
            if row['remember']:
                link = db.session.get(ProductPriceLink, row['source_key'])
                if link:
                    link.product_id = product.id
                else:
                    db.session.add(ProductPriceLink(source_key=row['source_key'], product_id=product.id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return len(selected)
