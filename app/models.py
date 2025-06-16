from app import db
from datetime import datetime

class Product(db.Model):
    """
    Modelo para los productos de inventario.
    """
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(100), nullable=False) # Marca del producto
    description = db.Column(db.String(255), nullable=False) # Descripción del producto
    wholesale_price = db.Column(db.Float, nullable=False) # Precio mayorista por unidad
    sale_percentage = db.Column(db.Float, nullable=False) # Porcentaje de venta (ej: 20 para 20%)
    total_sale_price = db.Column(db.Float, nullable=False) # Precio total de venta (calculado)

    # Relación uno a muchos con OrderItem (un producto puede estar en muchos items de pedido)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def __repr__(self):
        return f"<Product {self.description} ({self.brand})>"

class Order(db.Model):
    """
    Modelo para los pedidos al proveedor.
    """
    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.Date, nullable=False, default=datetime.utcnow) # Fecha del pedido
    total_order_price = db.Column(db.Float, nullable=False) # Suma total del pedido

    # Relación uno a muchos con OrderItem (un pedido puede tener muchos items)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.id} on {self.order_date}>"

class OrderItem(db.Model):
    """
    Modelo para los items individuales dentro de un pedido.
    Esto permite que un pedido tenga múltiples productos.
    """
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False) # ID del pedido al que pertenece
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True) # ID del producto del inventario (opcional, para referencia y autocompletado)

    # Datos del producto en el momento del pedido (no se actualizan si el producto original cambia)
    brand = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    wholesale_price_at_order = db.Column(db.Float, nullable=False) # Precio mayorista en el momento del pedido
    quantity = db.Column(db.Integer, nullable=False) # Cantidad de este producto en el pedido

    def __repr__(self):
        return f"<OrderItem {self.description} (x{self.quantity}) for Order {self.order_id}>"

