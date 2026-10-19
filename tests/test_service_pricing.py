import importlib
import json
import unittest
from copy import deepcopy
from datetime import date

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app import app, db
from app.models import Client, Product, Service
from app.service_pricing import calculate_color_pricing


def example():
    return {'kind': 'raiz', 'length': 'melena', 'labour': '10000', 'overhead': '2500', 'other_costs': '0', 'margin': '30', 'materials': [
        {'label': 'Tintura', 'package_cost': '12000', 'package_quantity': '60', 'quantity': '30', 'unit': 'g'},
        {'label': 'Oxidante', 'package_cost': '10000', 'package_quantity': '1000', 'quantity': '100', 'unit': 'ml'},
        {'label': 'Descartables', 'package_cost': '500', 'package_quantity': '1', 'quantity': '1', 'unit': 'unidad'},
    ]}


class PricingTests(unittest.TestCase):
    def test_example_and_margin_not_markup(self):
        result = calculate_color_pricing(example())
        self.assertEqual(result['material_total'], '7500.00')
        self.assertEqual(result['total_cost'], '20000.00')
        self.assertEqual(result['suggested_price'], '28571.43')

    def test_client_supplied_and_fractional_use(self):
        data = example()
        data['materials'][0]['client_supplied'] = True
        data['materials'][1]['quantity'] = '12.5'
        result = calculate_color_pricing(data)
        self.assertEqual(result['materials'][0]['cost'], '0.00')
        self.assertEqual(result['materials'][1]['cost'], '125.00')

    def test_application_without_materials_and_zero_margin(self):
        data = example()
        data.update(kind='aplicacion', materials=[], margin='0')
        self.assertEqual(calculate_color_pricing(data)['suggested_price'], '12500.00')

    def test_invalid_values(self):
        for value in ['NaN', 'Infinity', '-1', '1000000001', None, {}, 'abc']:
            data = example()
            data['labour'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_color_pricing(data)
        for field, value in [('margin', '100'), ('margin', '110'), ('materials', [None]), ('kind', 'bad')]:
            data = example()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                calculate_color_pricing(data)
        for field, value in [('package_quantity', 0), ('quantity', -1), ('unit', 'kg'), ('label', ''), ('client_supplied', 'true')]:
            data = example()
            data['materials'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                calculate_color_pricing(data)

    def test_migration_preserves_old_services(self):
        migration = importlib.import_module('migrations.versions.b4c7d2e9a610_agregar_calculo_de_coloracion')
        engine = create_engine('sqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE service (id INTEGER PRIMARY KEY, price FLOAT NOT NULL)'))
            connection.execute(text('INSERT INTO service VALUES (1, 20000)'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertIn('cost_breakdown', {column['name'] for column in inspect(connection).get_columns('service')})
                self.assertEqual(connection.execute(text('SELECT price, cost_breakdown FROM service')).one(), (20000, None))
                migration.downgrade()
                self.assertEqual(connection.execute(text('SELECT price FROM service')).scalar(), 20000)
        engine.dispose()


class ServicePricingRoutesTests(unittest.TestCase):
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
        self.client = Client(first_name='Ana', last_name='Perez')
        self.product = Product(brand='Marca', description='Tintura', wholesale_price=12000, sale_percentage=30, total_sale_price=15600, stock=10)
        db.session.add_all([self.client, self.product])
        db.session.commit()
        self.browser = app.test_client()
        self.path = f'/clients/{self.client.id}/services/add'

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def form_data(self):
        return {'date': '2026-10-19', 'description': 'Color de raiz', 'price': '29000', 'pricing_enabled': 'on', 'pricing_data': json.dumps(example())}

    def test_create_edit_snapshot_and_stock(self):
        data = self.form_data()
        data.update(product_ids=str(self.product.id), quantities_used='1')
        self.assertEqual(self.browser.post(self.path, data=data).status_code, 302)
        service = Service.query.one()
        original = deepcopy(service.cost_breakdown)
        self.assertEqual(original['suggested_price'], '28571.43')
        self.assertEqual(service.price, 29000)
        self.assertEqual(self.product.stock, 9)
        edit = f'/clients/{self.client.id}/services/edit/{service.id}'
        self.assertEqual(self.browser.get(edit).status_code, 200)
        self.product.wholesale_price = 99999
        db.session.commit()
        self.assertEqual(self.browser.post(edit, data=data).status_code, 302)
        self.assertEqual(service.cost_breakdown, original)
        self.assertEqual(self.product.stock, 9)

    def test_pricing_does_not_consume_whole_packages(self):
        self.browser.post(self.path, data=self.form_data())
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(len(Service.query.one().product_associations), 0)

    def test_server_recalculates_and_preserves_charged_price(self):
        data = self.form_data()
        forged = example()
        forged['suggested_price'] = '1'
        forged['total_cost'] = '0'
        data['pricing_data'] = json.dumps(forged)
        self.browser.post(self.path, data=data)
        service = Service.query.one()
        self.assertEqual(service.cost_breakdown['total_cost'], '20000.00')
        self.assertEqual(service.price, 29000)

    def test_invalid_form_retains_input_and_does_not_mutate(self):
        data = self.form_data()
        invalid = example()
        invalid['margin'] = 100
        data.update(pricing_data=json.dumps(invalid), product_ids=str(self.product.id), quantities_used='1')
        response = self.browser.post(self.path, data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Color de raiz', response.data)
        self.assertEqual(Service.query.count(), 0)
        self.assertEqual(self.product.stock, 10)
        data['pricing_data'] = json.dumps(example())
        data['quantities_used'] = '11'
        self.browser.post(self.path, data=data)
        self.assertEqual(Service.query.count(), 0)
        self.assertEqual(self.product.stock, 10)

    def test_manual_legacy_service_and_invalid_price(self):
        data = {'date': date.today().isoformat(), 'description': 'Corte', 'price': '5000'}
        self.browser.post(self.path, data=data)
        service = Service.query.one()
        self.assertIsNone(service.cost_breakdown)
        self.assertEqual(self.browser.get(f'/clients/{self.client.id}/services/edit/{service.id}').status_code, 200)
        data['price'] = 'NaN'
        response = self.browser.post(self.path, data=data)
        self.assertNotIn(b'type="checkbox" checked', response.data)
        self.assertEqual(Service.query.count(), 1)

    def test_repeated_stock_products_are_combined_and_invalid_edit_rolls_back(self):
        data = self.form_data()
        data.update(product_ids=[str(self.product.id)] * 2, quantities_used=['1', '2'])
        self.browser.post(self.path, data=data)
        service = Service.query.one()
        self.assertEqual(self.product.stock, 7)
        self.assertEqual(len(service.product_associations), 1)
        self.assertEqual(service.product_associations[0].quantity, 3)
        data.update(product_ids=str(self.product.id), quantities_used='11', price='1')
        self.browser.post(f'/clients/{self.client.id}/services/edit/{service.id}', data=data)
        self.assertEqual(self.product.stock, 7)
        self.assertEqual(service.price, 29000)
        self.assertEqual(service.product_associations[0].quantity, 3)

    def test_missing_stock_quantity_is_rejected(self):
        data = self.form_data()
        data['product_ids'] = str(self.product.id)
        self.browser.post(self.path, data=data)
        self.assertEqual(Service.query.count(), 0)
        self.assertEqual(self.product.stock, 10)


if __name__ == '__main__':
    unittest.main()
