from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models import Product, Order, OrderItem
from datetime import datetime, date

@app.route('/')
def index():
    """
    Ruta principal, redirige a la página de productos.
    """
    return redirect(url_for('products'))

# --- Rutas de Gestión de Productos ---

@app.route('/products')
def products():
    """
    Muestra la lista de productos y permite agregar/editar/eliminar.
    """
    products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    """
    Permite agregar un nuevo producto.
    """
    if request.method == 'POST':
        brand = request.form['brand']
        description = request.form['description']
        try:
            wholesale_price = float(request.form['wholesale_price'])
            sale_percentage = float(request.form['sale_percentage'])

            # Calcular el precio total de venta
            total_sale_price = wholesale_price * (1 + sale_percentage / 100)

            new_product = Product(
                brand=brand,
                description=description,
                wholesale_price=wholesale_price,
                sale_percentage=sale_percentage,
                total_sale_price=total_sale_price
            )
            db.session.add(new_product)
            db.session.commit()
            flash('Producto agregado exitosamente!', 'success')
            return redirect(url_for('products'))
        except ValueError:
            flash('Por favor, ingresa valores numéricos válidos para precio y porcentaje.', 'danger')
        except Exception as e:
            flash(f'Error al agregar producto: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_product.html', product=None, title='Agregar Producto')

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """
    Permite editar un producto existente.
    """
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.brand = request.form['brand']
        product.description = request.form['description']
        try:
            product.wholesale_price = float(request.form['wholesale_price'])
            product.sale_percentage = float(request.form['sale_percentage'])

            # Recalcular el precio total de venta
            product.total_sale_price = product.wholesale_price * (1 + product.sale_percentage / 100)

            db.session.commit()
            flash('Producto actualizado exitosamente!', 'success')
            return redirect(url_for('products'))
        except ValueError:
            flash('Por favor, ingresa valores numéricos válidos para precio y porcentaje.', 'danger')
        except Exception as e:
            flash(f'Error al actualizar producto: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_product.html', product=product, title='Editar Producto')

@app.route('/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """
    Permite eliminar un producto.
    """
    product = Product.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash('Producto eliminado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar producto: {e}', 'danger')
        db.session.rollback()
    return redirect(url_for('products'))

# --- Rutas de Gestión de Pedidos ---

@app.route('/orders', methods=['GET', 'POST'])
def orders():
    """
    Muestra la lista de pedidos, permite buscar por fecha y exportar a PDF.
    """
    orders_query = Order.query.order_by(Order.order_date.desc())
    search_from_date = request.args.get('from_date')
    search_to_date = request.args.get('to_date')

    if search_from_date:
        try:
            from_date_obj = datetime.strptime(search_from_date, '%Y-%m-%d').date()
            orders_query = orders_query.filter(Order.order_date >= from_date_obj)
        except ValueError:
            flash('Formato de fecha "Desde" inválido. Usa AAAA-MM-DD.', 'danger')
            search_from_date = '' # Clear invalid input
    
    if search_to_date:
        try:
            to_date_obj = datetime.strptime(search_to_date, '%Y-%m-%d').date()
            orders_query = orders_query.filter(Order.order_date <= to_date_obj)
        except ValueError:
            flash('Formato de fecha "Hasta" inválido. Usa AAAA-MM-DD.', 'danger')
            search_to_date = '' # Clear invalid input


    orders = orders_query.all()
    
    # Cargar los items de cada pedido para mostrarlos
    for order in orders:
        order.items_list = OrderItem.query.filter_by(order_id=order.id).all()

    return render_template('orders.html', 
                           orders=orders, 
                           from_date=search_from_date, 
                           to_date=search_to_date)


@app.route('/orders/add', methods=['GET', 'POST'])
def add_order():
    """
    Permite agregar un nuevo pedido.
    """
    products_for_dropdown = Product.query.all() # Para el select de productos

    if request.method == 'POST':
        order_date_str = request.form['order_date']
        try:
            order_date = datetime.strptime(order_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido. Por favor, usa AAAA-MM-DD.', 'danger')
            return render_template('add_order.html', products=products_for_dropdown)

        # Crear el nuevo pedido
        new_order = Order(order_date=order_date, total_order_price=0.0) # El total se actualizará
        db.session.add(new_order)
        db.session.flush() # Obtener el ID del pedido antes de commitear

        item_product_ids = request.form.getlist('product_id[]')
        item_brands = request.form.getlist('item_brand[]')
        item_descriptions = request.form.getlist('item_description[]')
        item_wholesale_prices = request.form.getlist('item_wholesale_price[]')
        item_quantities = request.form.getlist('item_quantity[]')

        total_order_price = 0.0
        
        # Procesar cada item del pedido
        for i in range(len(item_brands)):
            try:
                # Si el product_id es "0" significa que se ingresó manualmente o no se seleccionó un producto existente
                product_id_val = int(item_product_ids[i]) if item_product_ids[i] and item_product_ids[i] != '0' else None
                wholesale_price_at_order = float(item_wholesale_prices[i])
                quantity = int(item_quantities[i])

                if quantity <= 0:
                    flash(f'La cantidad para el producto "{item_descriptions[i]}" debe ser mayor que cero.', 'danger')
                    db.session.rollback()
                    return render_template('add_order.html', products=products_for_dropdown)

                item_total = wholesale_price_at_order * quantity
                total_order_price += item_total

                new_order_item = OrderItem(
                    order_id=new_order.id,
                    product_id=product_id_val,
                    brand=item_brands[i],
                    description=item_descriptions[i],
                    wholesale_price_at_order=wholesale_price_at_order,
                    quantity=quantity
                )
                db.session.add(new_order_item)
            except ValueError:
                flash('Valores inválidos para precio o cantidad en los items del pedido.', 'danger')
                db.session.rollback()
                return render_template('add_order.html', products=products_for_dropdown)
            except Exception as e:
                flash(f'Error al procesar item de pedido: {e}', 'danger')
                db.session.rollback()
                return render_template('add_order.html', products=products_for_dropdown)
        
        new_order.total_order_price = total_order_price
        db.session.commit()
        flash('Pedido agregado exitosamente!', 'success')
        return redirect(url_for('orders'))

    return render_template('add_order.html', products=products_for_dropdown)


# --- API Endpoints ---

@app.route('/api/products_list')
def products_list_api():
    """
    API endpoint para obtener la lista de productos (ID y descripción) para el dropdown.
    """
    # Se modificó para incluir 'brand' y 'wholesale_price' en la selección de entidades
    products = Product.query.with_entities(Product.id, Product.description, Product.brand, Product.wholesale_price).all()
    # Retorna una lista de diccionarios, útil para JavaScript
    return jsonify([{'id': p.id, 'description': p.description, 'brand': p.brand, 'wholesale_price': p.wholesale_price} for p in products])

@app.route('/api/product_details/<int:product_id>')
def product_details_api(product_id):
    """
    API endpoint para obtener los detalles de un producto específico (para autocompletado).
    """
    product = Product.query.get(product_id)
    if product:
        return jsonify({
            'brand': product.brand,
            'description': product.description,
            'wholesale_price': product.wholesale_price
        })
    return jsonify({'error': 'Producto no encontrado'}), 404

