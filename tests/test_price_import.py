import importlib
import time
import unittest
from datetime import datetime
from io import BytesIO
from html import unescape
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from alembic.migration import MigrationContext
from alembic.operations import Operations
from openpyxl import Workbook
from sqlalchemy import create_engine, inspect, text

from app import app, db
from app.models import Product, ProductPriceLink, Client, Service, Order, OrderItem
from app.price_import import read_price_workbook, match_prices, parse_price, load_draft, apply_prices


def workbook_bytes(description='Tintura x60ml MARCA', price=200, brand='MARCA', code='00123', count=1):
    book = Workbook()
    sheet = book.active
    sheet.title = 'marca 2026-05 D'
    sheet.append([None, brand, None, datetime(2026, 5, 1)])
    sheet.append(['COD BARRA', 'DESCRIPCION', 'COD PROV', 'DISTR'])
    sheet.append([None, 'COLORACION', None, None])
    for index in range(count):
        sheet.append([code if index == 0 else str(index), description if index == 0 else f'Producto {index}', None, price])
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


class PriceParserTests(unittest.TestCase):
    def test_supplier_format_and_dates(self):
        parsed = read_price_workbook(workbook_bytes(price=1234.567))
        row = parsed['rows'][0]
        self.assertEqual(len(parsed['rows']), 1)
        self.assertEqual(row['price'], '1234.57')
        self.assertEqual(row['barcode'], '00123')
        self.assertEqual(row['list_date'], '2026-05-01')
        self.assertEqual(row['row'], 4)

    def test_prices_and_invalid_values(self):
        self.assertEqual(parse_price('$ 1.234,56'), '1234.56')
        self.assertEqual(parse_price('1.234'), '1234.00')
        self.assertEqual(parse_price('1234.56'), '1234.56')
        for value in [0, -1, True, float('nan'), float('inf'), '=1+1', 'consultar', '0,001', 1000000001]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_price(value)

    def test_uncached_formula_cannot_zero_a_price(self):
        with self.assertRaises(ValueError):
            read_price_workbook(workbook_bytes(price='=100*2'))

    def test_invalid_files_and_zip_limits(self):
        with self.assertRaises(ValueError):
            read_price_workbook(b'not an Excel file')
        content = BytesIO()
        with ZipFile(content, 'w') as archive:
            archive.writestr('bomb', b'a' * 100)
        with patch('app.price_import.MAX_UPLOAD', 5), self.assertRaises(ValueError):
            read_price_workbook(content.getvalue())

    def test_wide_formatting_is_bounded(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['Marca', 'Descripcion', 'Precio mayorista'])
        sheet.append(['Marca', 'Tintura', 100])
        sheet.cell(2, 16036, 'unused formatting')
        stream = BytesIO()
        book.save(stream)
        self.assertEqual(read_price_workbook(stream.getvalue())['rows'][0]['price'], '100.00')
        book.close()

    def test_migration_preserves_products(self):
        migration = importlib.import_module('migrations.versions.d6e9f4a1c832_agregar_vinculos_de_listas_excel')
        engine = create_engine('sqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE product (id INTEGER PRIMARY KEY, stock INTEGER, wholesale_price FLOAT)'))
            connection.execute(text('INSERT INTO product VALUES (1, 5, 100)'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertIn('product_price_link', inspect(connection).get_table_names())
                self.assertEqual(tuple(connection.execute(text('SELECT * FROM product')).one()), (1, 5, 100))
                migration.downgrade()
                self.assertNotIn('product_price_link', inspect(connection).get_table_names())
        engine.dispose()


class PriceImportRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = app.app_context()
        cls.context.push()
        cls.original_engine = db.engines[None]
        db.engines[None] = create_engine('sqlite:///:memory:')

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.engines[None].dispose()
        db.engines[None] = cls.original_engine
        cls.context.pop()

    def setUp(self):
        db.create_all()
        self.directory = TemporaryDirectory()
        self.instance = patch.object(app, 'instance_path', self.directory.name)
        self.instance.start()
        self.product = Product(brand='Marca', description='Tintura x60ml MARCA', wholesale_price=100, sale_percentage=30, total_sale_price=130, stock=5)
        self.client = Client(first_name='Ana', last_name='Perez')
        db.session.add_all([self.product, self.client])
        db.session.commit()
        self.browser = app.test_client()
        self.path = '/products/prices/import'

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.instance.stop()
        self.directory.cleanup()

    def upload(self, content=None):
        response = self.browser.post(self.path, data={'action': 'upload', 'file': (BytesIO(content or workbook_bytes()), 'lista.xlsx')}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 302)
        with self.browser.session_transaction() as session:
            token = session['product_price_import']
        return token, load_draft(token)

    def test_preview_does_not_change_prices_and_confirmation_preserves_history(self):
        service = Service(client_id=self.client.id, description='Color anterior', price=1000, cost_breakdown={'total_cost': '100.00'})
        order = Order(total_order_price=100)
        order.items.append(OrderItem(product=self.product, brand='Marca', description='Tintura', quantity=1, wholesale_price_at_order=100))
        db.session.add_all([service, order])
        db.session.commit()
        token, draft = self.upload()
        self.assertEqual(self.product.wholesale_price, 100)
        self.assertEqual(draft['rows'][0]['product_id'], self.product.id)
        self.assertEqual(self.browser.get(self.path).status_code, 200)
        self.assertEqual(self.browser.post(self.path, data={'action': 'apply', 'token': token}).status_code, 302)
        db.session.expire_all()
        self.assertEqual(self.product.wholesale_price, 200)
        self.assertEqual(self.product.total_sale_price, 260)
        self.assertEqual(self.product.sale_percentage, 30)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(service.cost_breakdown, {'total_cost': '100.00'})
        self.assertEqual(order.items[0].wholesale_price_at_order, 100)
        self.assertEqual(ProductPriceLink.query.count(), 1)

    def test_manual_mapping_is_remembered_for_future_prices(self):
        token, draft = self.upload(workbook_bytes(description='Nombre diferente'))
        self.assertIsNone(draft['rows'][0]['product_id'])
        self.browser.post(self.path, data={'action': 'apply', 'token': token, 'row_0': str(self.product.id)})
        self.assertEqual(self.product.wholesale_price, 100)
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        _, next_draft = self.upload(workbook_bytes(description='Otro nombre nuevo', price=300))
        self.assertEqual(next_draft['rows'][0]['product_id'], self.product.id)
        self.assertEqual(next_draft['rows'][0]['reason'], 'Vinculo guardado')

    def test_tampered_prices_are_ignored_and_nonce_required(self):
        token, _ = self.upload()
        self.browser.post(self.path, data={'action': 'apply', 'token': 'wrong'})
        self.assertEqual(self.product.wholesale_price, 100)
        self.browser.post(self.path, data={'action': 'apply', 'token': token, 'price': '1'})
        db.session.expire_all()
        self.assertEqual(self.product.wholesale_price, 200)

    def test_stale_product_and_duplicate_selection_are_rejected(self):
        token, draft = self.upload()
        self.product.wholesale_price = 150
        db.session.commit()
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(self.product.wholesale_price, 150)
        token, draft = self.upload(workbook_bytes(count=2))
        self.browser.post(self.path, data={'action': 'apply', 'token': token, 'row_1': self.product.id})
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(self.product.wholesale_price, 150)
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_expiry_and_pagination(self):
        token, draft = self.upload(workbook_bytes(count=60))
        self.assertEqual(self.browser.post(self.path + '?action=review', data={'token': token, 'page_to': '2', 'status': 'all'}).status_code, 302)
        self.assertIn('P\u00e1gina 2 de 2', unescape(self.browser.get(self.path + '?status=all&page=2').get_data(as_text=True)))
        with patch('app.price_import.time.time', return_value=time.time() + 3601), self.assertRaises(ValueError):
            load_draft(token)

    def test_product_delete_removes_links(self):
        db.session.add(ProductPriceLink(source_key='a' * 64, product=self.product))
        db.session.commit()
        db.session.delete(self.product)
        db.session.commit()
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_ambiguous_names_do_not_auto_match(self):
        db.session.add(Product(brand='Marca', description='Tintura x60ml MARCA', wholesale_price=100, sale_percentage=30, total_sale_price=130, stock=2))
        db.session.commit()
        _, draft = self.upload()
        self.assertIsNone(draft['rows'][0]['product_id'])
        self.assertEqual(draft['rows'][0]['reason'], 'Coincidencia ambigua')

    def test_changed_stock_is_preserved_and_failed_batch_is_atomic(self):
        second = Product(brand='Marca', description='Producto 1', wholesale_price=50, sale_percentage=20, total_sale_price=60, stock=2)
        db.session.add(second)
        db.session.commit()
        token, draft = self.upload(workbook_bytes(count=2))
        self.product.stock = 4
        second.wholesale_price = 75
        db.session.commit()
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        db.session.expire_all()
        self.assertEqual(self.product.wholesale_price, 100)
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(ProductPriceLink.query.count(), 0)
        token, _ = self.upload()
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        db.session.expire_all()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.product.wholesale_price, 200)

    def select_new(self, token, index=0, description='Champu nuevo', percentage='25'):
        return self.browser.post(self.path, data={'action': 'review', 'token': token,
            f'row_{index}': 'new', f'new_brand_{index}': 'Marca',
            f'new_description_{index}': description, f'new_percentage_{index}': percentage})

    def test_create_selected_product_with_zero_stock_and_remember_it(self):
        token, _ = self.upload(workbook_bytes(description='Champu proveedor', code='new-123'))
        self.select_new(token)
        self.assertEqual(Product.query.count(), 1)
        preview = self.browser.get(self.path)
        self.assertIn(b'Champu nuevo', preview.data)
        self.assertIn(b'250,00', preview.data)
        self.browser.post(self.path, data={'action': 'apply', 'token': token, 'stock': '999', 'price': '1'})
        created = Product.query.filter_by(description='Champu nuevo').one()
        self.assertEqual(created.stock, 0)
        self.assertEqual(created.wholesale_price, 200)
        self.assertEqual(created.sale_percentage, 25)
        self.assertEqual(created.total_sale_price, 250)
        self.assertEqual(self.product.stock, 5)
        token, next_draft = self.upload(workbook_bytes(description='Proveedor renombrado', code='new-123', price=300))
        self.assertEqual(next_draft['rows'][0]['product_id'], created.id)
        created.stock = 7
        db.session.commit()
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        db.session.expire_all()
        self.assertEqual(Product.query.count(), 2)
        self.assertEqual(created.stock, 7)
        self.assertEqual(created.total_sale_price, 375)

    def test_creating_existing_product_is_rejected(self):
        token, _ = self.upload()
        self.select_new(token, description=self.product.description)
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(Product.query.count(), 1)
        self.assertEqual(self.product.wholesale_price, 100)
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_mixed_batch_updates_existing_and_creates_only_selected_new(self):
        token, _ = self.upload(workbook_bytes(count=3))
        self.select_new(token, index=1, description='Producto nuevo elegido', percentage='50')
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        db.session.expire_all()
        self.assertEqual(Product.query.count(), 2)
        created = Product.query.filter_by(description='Producto nuevo elegido').one()
        self.assertEqual(created.stock, 0)
        self.assertEqual(created.total_sale_price, 300)
        self.assertEqual(self.product.wholesale_price, 200)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(ProductPriceLink.query.count(), 2)

    def test_duplicate_new_products_roll_back_whole_batch(self):
        token, _ = self.upload(workbook_bytes(description='Desconocido', count=2))
        self.select_new(token, index=0, description='Mismo nombre')
        self.select_new(token, index=1, description='Mismo nombre')
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(Product.query.count(), 1)
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_invalid_new_percentage_rolls_back_existing_price_update(self):
        token, _ = self.upload(workbook_bytes(count=2))
        self.select_new(token, index=1, percentage='NaN')
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        db.session.expire_all()
        self.assertEqual(Product.query.count(), 1)
        self.assertEqual(self.product.wholesale_price, 100)
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_existing_product_added_since_preview_prevents_duplicate_creation(self):
        token, _ = self.upload(workbook_bytes(description='Champu nuevo', code='new-123'))
        self.select_new(token)
        db.session.add(Product(brand='Marca', description='Champu nuevo', wholesale_price=150, sale_percentage=10, total_sale_price=165, stock=3))
        db.session.commit()
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(Product.query.count(), 2)
        self.assertEqual(ProductPriceLink.query.count(), 0)

    def test_new_selection_requires_review_before_creating(self):
        token, _ = self.upload(workbook_bytes(description='Nuevo', code='new-123'))
        self.browser.post(self.path, data={'action': 'apply', 'token': token,
            'row_0': 'new', 'new_brand_0': 'Marca', 'new_description_0': 'Champu nuevo', 'new_percentage_0': '20'})
        self.assertEqual(Product.query.count(), 1)
        self.browser.post(self.path, data={'action': 'apply', 'token': token})
        self.assertEqual(Product.query.count(), 2)


if __name__ == '__main__':
    unittest.main()
