from io import BytesIO
from tempfile import TemporaryDirectory

from flask import send_file, request
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import app, db
from app.models import Product
from tests.test_price_import import workbook_bytes


if __name__ == '__main__':
    directory = TemporaryDirectory()
    app.instance_path = directory.name
    with app.app_context():
        db.engines[None] = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        db.create_all()
        db.session.add(Product(brand='Marca', description='Tintura x60ml MARCA', wholesale_price=100, sale_percentage=30, total_sale_price=130, stock=5))
        db.session.commit()

    @app.get('/__test/list.xlsx')
    def fixture_list():
        if request.args.get('unmatched'):
            description = 'Nombre actualizado del proveedor' if request.args.get('rename') else 'Nombre distinto del proveedor'
            return send_file(BytesIO(workbook_bytes(description=description, price=300, code='other-code')), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        return send_file(BytesIO(workbook_bytes(count=60)), mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    app.run(host='127.0.0.1', port=5073, threaded=False)
