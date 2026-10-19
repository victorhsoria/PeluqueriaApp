from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import app, db
from app.models import Client, Product


if __name__ == '__main__':
    with app.app_context():
        db.engines[None] = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        db.create_all()
        db.session.add(Client(first_name='Ana', last_name='Perez'))
        db.session.add(Product(brand='Marca', description='Tintura 60 g', wholesale_price=12000, sale_percentage=30, total_sale_price=15600, stock=10))
        db.session.commit()
    app.run(host='127.0.0.1', port=5065, threaded=False)
