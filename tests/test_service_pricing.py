import importlib
import json
import unittest
from copy import deepcopy
from datetime import date

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app import app, db
from app.models import Client, Product, Service, ServiceTemplate
from app.service_pricing import calculate_color_pricing
from app.service_examples import bucles_color_examples


def example():
    return {'kind': 'raiz', 'length': 'melena', 'labour': '10000', 'overhead': '2500', 'other_costs': '0', 'margin': '30', 'materials': [
        {'label': 'Tintura', 'package_cost': '12000', 'package_quantity': '60', 'quantity': '30', 'unit': 'g'},
        {'label': 'Oxidante', 'package_cost': '10000', 'package_quantity': '1000', 'quantity': '100', 'unit': 'ml'},
        {'label': 'Descartables', 'package_cost': '500', 'package_quantity': '1', 'quantity': '1', 'unit': 'unidad'},
    ]}


class PricingTests(unittest.TestCase):
    def test_reference_prices_are_not_internal_costs(self):
        examples = list(bucles_color_examples())
        self.assertEqual(len(examples), 6)
        self.assertEqual([data['reference_price'] for _, data in examples], ['39999.00', '44999.00', '49999.00', '54999.00', '59999.00', '19999.00'])
        for _, data in examples:
            self.assertFalse(data['costs_confirmed'])
            self.assertEqual(data['materials'], [])
            self.assertEqual(data['labour'], '0.00')
            self.assertEqual(calculate_color_pricing(data), data)

    def test_invalid_reference_and_verification_state(self):
        for value in ['NaN', '-1', 'Infinity', '1000000001']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate_color_pricing(dict(example(), reference_price=value))
        with self.assertRaises(ValueError):
            calculate_color_pricing(dict(example(), costs_confirmed='false'))

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

    def test_template_migration_does_not_change_service_prices(self):
        migration = importlib.import_module('migrations.versions.c5d8e3f0b721_agregar_plantillas_de_servicios')
        engine = create_engine('sqlite:///:memory:')
        with engine.begin() as connection:
            connection.execute(text('CREATE TABLE service (id INTEGER PRIMARY KEY, price FLOAT NOT NULL)'))
            connection.execute(text('INSERT INTO service VALUES (1, 29000)'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertIn('service_template', inspect(connection).get_table_names())
                self.assertEqual(connection.execute(text('SELECT price FROM service')).scalar(), 29000)
                migration.downgrade()
                self.assertNotIn('service_template', inspect(connection).get_table_names())
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
        self.assertNotIn(b'id="pricing-enabled" name="pricing_enabled" type="checkbox" checked', response.data)
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

    def test_bucles_examples_are_idempotent_and_do_not_overwrite(self):
        own = ServiceTemplate(name='Mi servicio', pricing=calculate_color_pricing(example()))
        db.session.add(own)
        db.session.commit()
        original = deepcopy(own.pricing)
        self.assertEqual(self.browser.post('/service-templates/examples/bucles').status_code, 302)
        self.assertEqual(ServiceTemplate.query.count(), 7)
        seeded = ServiceTemplate.query.filter(ServiceTemplate.id != own.id).first()
        custom = dict(seeded.pricing, reference_price='35000.00')
        seeded.name = 'Mi ejemplo adaptado'
        seeded.pricing = custom
        db.session.commit()
        self.browser.post('/service-templates/examples/bucles')
        self.assertEqual(ServiceTemplate.query.count(), 7)
        self.assertEqual(seeded.pricing['reference_price'], '35000.00')
        self.assertEqual(own.pricing, original)
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(Service.query.count(), 0)

    def test_unverified_example_does_not_replace_real_costs(self):
        name, pricing = next(bucles_color_examples())
        template = ServiceTemplate(name=name, pricing=pricing)
        db.session.add(template)
        db.session.commit()
        config = dict(example(), template_id=template.id)
        response = self.browser.post('/api/service-pricing/refresh', json=config).get_json()
        self.assertEqual(response['pricing']['labour'], '10000.00')
        self.assertEqual(response['pricing']['margin'], '30')
        self.assertEqual(response['pricing']['reference_price'], '39999.00')
        self.assertTrue(response['warnings'])
        self.assertEqual(response['changes'][0]['label'], 'Precio de referencia')
        self.assertIsNone(response['changes'][0]['before'])

    def test_unverified_example_can_set_price_without_fake_profit(self):
        name, pricing = next(bucles_color_examples())
        data = self.form_data()
        data.update(price='39999', pricing_data=json.dumps(pricing))
        self.browser.post(self.path, data=data)
        service = Service.query.one()
        self.assertFalse(service.cost_breakdown['costs_confirmed'])
        self.assertEqual(service.price, 39999)
        response = self.browser.get(f'/clients/{self.client.id}')
        self.assertIn(b'Costos sin verificar.', response.data)
        self.assertNotIn(b'Precio sugerido: $ 0.00', response.data)

    def test_template_create_edit_and_name_validation(self):
        data = {'template_name': 'Raiz melena', 'pricing_enabled': 'on', 'pricing_data': json.dumps(example())}
        self.assertEqual(self.browser.get('/service-templates/add').status_code, 200)
        self.assertEqual(self.browser.post('/service-templates/add', data=data).status_code, 302)
        template = ServiceTemplate.query.one()
        self.assertEqual(self.browser.get('/service-templates').status_code, 200)
        self.assertEqual(self.browser.get(f'/service-templates/{template.id}/edit').status_code, 200)
        self.assertEqual(self.product.stock, 10)
        data['template_name'] = 'raiz melena'
        self.assertEqual(self.browser.post('/service-templates/add', data=data).status_code, 200)
        self.assertEqual(ServiceTemplate.query.count(), 1)
        data['template_name'] = ''
        self.browser.post('/service-templates/add', data=data)
        self.assertEqual(ServiceTemplate.query.count(), 1)

    def test_template_prices_are_current_and_history_is_unchanged(self):
        config = example()
        config['materials'][0]['product_id'] = self.product.id
        template = ServiceTemplate(name='Raiz', pricing=calculate_color_pricing(config))
        db.session.add(template)
        db.session.commit()
        config['template_id'] = template.id
        data = self.form_data()
        data['pricing_data'] = json.dumps(config)
        self.browser.post(self.path, data=data)
        service = Service.query.one()
        original = deepcopy(service.cost_breakdown)
        self.product.wholesale_price = 18000
        updated = example()
        updated['materials'][0]['product_id'] = self.product.id
        updated['labour'] = '12000'
        template.pricing = calculate_color_pricing(updated)
        db.session.commit()
        current = self.browser.get(f'/api/service-templates/{template.id}').get_json()
        self.assertEqual(current['pricing']['materials'][0]['package_cost'], '18000.00')
        self.assertEqual(current['pricing']['labour'], '12000.00')
        preview = self.browser.post('/api/service-pricing/refresh', json=original).get_json()
        self.assertEqual(len(preview['changes']), 2)
        self.assertEqual(preview['pricing']['total_cost'], '25000.00')
        self.assertEqual(preview['pricing']['materials'][0]['quantity'], '30')
        self.assertEqual(service.cost_breakdown, original)
        self.assertEqual(service.price, 29000)
        data['pricing_data'] = json.dumps(preview['pricing'])
        self.browser.post(f'/clients/{self.client.id}/services/edit/{service.id}', data=data)
        self.assertEqual(service.cost_breakdown['total_cost'], '25000.00')
        self.assertEqual(service.price, 29000)

    def test_refresh_deleted_template_and_products_preserves_snapshot(self):
        config = example()
        config['template_id'] = 999
        config['materials'][0]['product_id'] = 999
        preview = self.browser.post('/api/service-pricing/refresh', json=config).get_json()
        self.assertEqual(len(preview['warnings']), 2)
        self.assertEqual(preview['pricing']['total_cost'], '20000.00')
        self.assertEqual(preview['changes'], [])
        self.assertEqual(self.browser.post('/api/service-pricing/refresh', json={'margin': 100}).status_code, 400)
        self.assertEqual(self.browser.post('/api/service-pricing/refresh', json=[]).status_code, 400)

    def test_refresh_keeps_custom_consumption_and_client_supplied_products(self):
        config = example()
        config['materials'][0].update(product_id=self.product.id, quantity='42.5', client_supplied=True)
        config['labour'] = '15000'
        self.product.wholesale_price = 18000
        db.session.commit()
        response = self.browser.post('/api/service-pricing/refresh', json=config).get_json()
        row = response['pricing']['materials'][0]
        self.assertEqual(row['quantity'], '42.5')
        self.assertTrue(row['client_supplied'])
        self.assertEqual(row['cost'], '0.00')
        self.assertEqual(response['pricing']['labour'], '15000.00')
        self.assertEqual(self.product.stock, 10)

    def test_delete_template_does_not_delete_work(self):
        template = ServiceTemplate(name='Raiz', pricing=calculate_color_pricing(example()))
        db.session.add(template)
        db.session.commit()
        data = self.form_data()
        config = example()
        config['template_id'] = template.id
        data['pricing_data'] = json.dumps(config)
        self.browser.post(self.path, data=data)
        original = deepcopy(Service.query.one().cost_breakdown)
        self.assertEqual(self.browser.post(f'/service-templates/{template.id}/delete').status_code, 302)
        self.assertEqual(ServiceTemplate.query.count(), 0)
        self.assertEqual(Service.query.one().cost_breakdown, original)
        self.assertEqual(self.product.stock, 10)


if __name__ == '__main__':
    unittest.main()
