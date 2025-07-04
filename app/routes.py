from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models import Product, Order, OrderItem, Client, Appointment, Service
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func, extract
import locale # Importar el módulo locale

# Configurar la configuración regional a español para el formato de fechas
# Esto es crucial para que strftime devuelva los nombres de días y meses en español.
# 'es_ES.UTF-8' es común en sistemas Linux. En Windows, podría ser 'Spanish_Spain.1252' o 'es_ES'.
# PythonAnywhere suele ser Linux, así que 'es_ES.UTF-8' debería funcionar.
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    # Fallback para sistemas donde 'es_ES.UTF-8' no esté disponible
    # Puedes probar otras opciones como 'es_ES' o 'Spanish_Spain.1252' si es necesario
    print("Advertencia: No se pudo establecer la configuración regional 'es_ES.UTF-8'. Las fechas podrían no mostrarse en español.")
    # Si estás en Windows y esto falla, intenta con:
    # locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
    pass


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
    También muestra los turnos del día actual.
    """
    products = Product.query.all()

    # Obtener la fecha de hoy
    today = date.today()
    
    # Formatear la fecha de hoy para mostrarla en la plantilla
    # Ahora, gracias a locale.setlocale, strftime debería devolver el formato en español
    today_formatted = today.strftime('%A, %d de %B')

    # Consultar los turnos para hoy, ordenados por hora
    today_appointments = Appointment.query.join(Client).filter(
        func.date(Appointment.date_time) == today
    ).order_by(Appointment.date_time).all()

    # Formatear los turnos para la visualización en la plantilla
    formatted_today_appointments = []
    for appt in today_appointments:
        formatted_today_appointments.append({
            'time': appt.date_time.strftime('%H:%M'),
            'client_name': f"{appt.client.first_name} {appt.client.last_name}",
            'description': appt.description,
            'client_id': appt.client.id,
            'appointment_id': appt.id
        })

    return render_template('products.html', 
                           products=products,
                           today_appointments=formatted_today_appointments,
                           today_formatted_date=today_formatted) # Pasar la fecha formateada

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

# --- Rutas de Gestión de Clientes ---

@app.route('/clients')
def clients():
    """
    Muestra la lista de clientes.
    """
    clients = Client.query.order_by(Client.last_name, Client.first_name).all()
    return render_template('clients.html', clients=clients)

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    """
    Permite agregar un nuevo cliente.
    """
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        address = request.form.get('address')
        phone = request.form.get('phone')

        new_client = Client(first_name=first_name, last_name=last_name,
                            address=address, phone=phone)
        try:
            db.session.add(new_client)
            db.session.commit()
            flash('Cliente agregado exitosamente!', 'success')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Error al agregar cliente: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_client.html', client=None, title='Agregar Cliente')

@app.route('/clients/edit/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    """
    Permite editar un cliente existente.
    """
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.first_name = request.form['first_name']
        client.last_name = request.form['last_name']
        client.address = request.form.get('address')
        client.phone = request.form.get('phone')
        try:
            db.session.commit()
            flash('Cliente actualizado exitosamente!', 'success')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Error al actualizar cliente: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_client.html', client=client, title='Editar Cliente')

@app.route('/clients/delete/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    """
    Permite eliminar un cliente.
    """
    client = Client.query.get_or_404(client_id)
    try:
        db.session.delete(client)
        db.session.commit()
        flash('Cliente eliminado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar cliente: {e}', 'danger')
        db.session.rollback()
    return redirect(url_for('clients'))

@app.route('/clients/<int:client_id>')
def client_detail(client_id):
    """
    Muestra los detalles de un cliente específico, sus turnos y trabajos.
    """
    client = Client.query.get_or_404(client_id)
    # Los turnos y servicios se cargan automáticamente debido a las relaciones en el modelo
    return render_template('client_detail.html', client=client, title=f'Detalle de {client.first_name} {client.last_name}')

# --- Rutas de Gestión de Turnos (Appointments) ---

@app.route('/clients/<int:client_id>/appointments/add', methods=['GET', 'POST'])
def add_appointment(client_id):
    """
    Permite agregar un nuevo turno para un cliente.
    """
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        date_time_str = request.form['date_time']
        description = request.form['description']
        try:
            # Combina la fecha y hora para crear un objeto datetime
            date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
            
            new_appointment = Appointment(client_id=client.id, date_time=date_time_obj, description=description)
            db.session.add(new_appointment)
            db.session.commit()
            flash('Turno agregado exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))
        except ValueError:
            flash('Formato de fecha y/o hora inválido. Usa AAAA-MM-DDTHH:MM.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'Error al agregar turno: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_appointment.html', client=client, appointment=None, title=f'Agregar Turno para {client.first_name}')

@app.route('/clients/<int:client_id>/appointments/edit/<int:appointment_id>', methods=['GET', 'POST'])
def edit_appointment(client_id, appointment_id):
    """
    Permite editar un turno existente de un cliente.
    """
    client = Client.query.get_or_404(client_id)
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.client_id != client_id: # Asegurar que el turno pertenece a este cliente
        flash('Turno no encontrado para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))

    if request.method == 'POST':
        appointment.date_time = datetime.strptime(request.form['date_time'], '%Y-%m-%dT%H:%M')
        appointment.description = request.form['description']
        try:
            db.session.commit()
            flash('Turno actualizado exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))
        except ValueError:
            flash('Formato de fecha y/o hora inválido. Usa AAAA-MM-DDTHH:MM.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'Error al actualizar turno: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_appointment.html', client=client, appointment=appointment, title=f'Editar Turno para {client.first_name}')

@app.route('/clients/<int:client_id>/appointments/delete/<int:appointment_id>', methods=['POST'])
def delete_appointment(client_id, appointment_id):
    """
    Permite eliminar un turno de un cliente.
    """
    client = Client.query.get_or_404(client_id)
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.client_id != client_id:
        flash('Turno no encontrado para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))
    try:
        db.session.delete(appointment)
        db.session.commit()
        flash('Turno eliminado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar turno: {e}', 'danger')
        db.session.rollback()
    return redirect(url_for('client_detail', client_id=client.id))

# --- Rutas de Gestión de Trabajos (Services) ---

@app.route('/clients/<int:client_id>/services/add', methods=['GET', 'POST'])
def add_service(client_id):
    """
    Permite agregar un nuevo trabajo/servicio realizado para un cliente.
    """
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        date_str = request.form['date']
        description = request.form['description']
        try:
            price = float(request.form['price'])
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            new_service = Service(client_id=client.id, date=date_obj, description=description, price=price)
            db.session.add(new_service)
            db.session.commit()
            flash('Trabajo/Servicio agregado exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))
        except ValueError:
            flash('Formato de fecha o precio inválido. Usa AAAA-MM-DD para la fecha y un número para el precio.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'Error al agregar trabajo/servicio: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_service.html', client=client, service=None, title=f'Agregar Trabajo para {client.first_name}')

@app.route('/clients/<int:client_id>/services/edit/<int:service_id>', methods=['GET', 'POST'])
def edit_service(client_id, service_id):
    """
    Permite editar un trabajo/servicio existente de un cliente.
    """
    client = Client.query.get_or_404(client_id)
    service = Service.query.get_or_404(service_id)
    if service.client_id != client_id: # Asegurar que el servicio pertenece a este cliente
        flash('Trabajo/Servicio no encontrado para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))

    if request.method == 'POST':
        service.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        service.description = request.form['description']
        try:
            service.price = float(request.form['price'])
            db.session.commit()
            flash('Trabajo/Servicio actualizado exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))
        except ValueError:
            flash('Formato de fecha o precio inválido. Usa AAAA-MM-DD para la fecha y un número para el precio.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'Error al actualizar trabajo/servicio: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_service.html', client=client, service=service, title=f'Editar Trabajo para {client.first_name}')

@app.route('/clients/<int:client_id>/services/delete/<int:service_id>', methods=['POST'])
def delete_service(client_id, service_id):
    """
    Permite eliminar un trabajo/servicio de un cliente.
    """
    client = Client.query.get_or_404(client_id)
    service = Service.query.get_or_404(service_id)
    if service.client_id != client_id:
        flash('Trabajo/Servicio no encontrado para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))
    try:
        db.session.delete(service)
        db.session.commit()
        flash('Trabajo/Servicio eliminado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar trabajo/servicio: {e}', 'danger')
        db.session.rollback()
    return redirect(url_for('client_detail', client_id=client.id))

# --- Ruta para Estadísticas de Clientes ---
@app.route('/clients/stats')
def client_stats():
    """
    Muestra estadísticas de ingresos por servicios de clientes, con filtros por mes y año.
    """
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)

    # Obtener todos los años y meses únicos de los servicios registrados
    available_years = db.session.query(extract('year', Service.date)).distinct().order_by(extract('year', Service.date).desc()).all()
    available_years = [y[0] for y in available_years]

    available_months = db.session.query(extract('month', Service.date)).distinct().order_by(extract('month', Service.date)).all()
    available_months = [m[0] for m in available_months]

    # Consulta base para servicios
    services_query = Service.query

    # Aplicar filtros si se seleccionaron mes y año
    if selected_year:
        services_query = services_query.filter(extract('year', Service.date) == selected_year)
    if selected_month:
        services_query = services_query.filter(extract('month', Service.date) == selected_month)

    # Calcular el total de ingresos de los servicios filtrados
    total_revenue = services_query.with_entities(func.sum(Service.price)).scalar() or 0.0

    # Calcular ingresos por cliente para los servicios filtrados
    revenue_by_client = services_query.join(Client).group_by(Client.id).with_entities(
        Client.first_name,
        Client.last_name,
        func.sum(Service.price)
    ).order_by(func.sum(Service.price).desc()).all()


    # Mapeo de números de mes a nombres (para mostrar en la plantilla)
    month_names = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    return render_template('client_stats.html', 
                           total_revenue=total_revenue,
                           revenue_by_client=revenue_by_client,
                           available_years=available_years,
                           available_months=available_months,
                           selected_year=selected_year,
                           selected_month=selected_month,
                           month_names=month_names,
                           title='Estadísticas de Clientes')

# --- Rutas de Calendario y API de Turnos ---

@app.route('/appointments/calendar')
def appointments_calendar():
    """
    Muestra el calendario de turnos.
    """
    return render_template('appointments_calendar.html', title='Calendario de Turnos')

@app.route('/api/appointments')
def api_appointments():
    """
    API endpoint para obtener todos los turnos.
    Retorna una lista de diccionarios con los detalles de cada turno.
    """
    # Usamos with_entities para seleccionar explícitamente las columnas que necesitamos,
    # incluyendo el ID del cliente y la descripción del turno.
    appointments = db.session.query(
        Appointment.id,
        Appointment.date_time,
        Appointment.description, # Incluir la descripción del turno
        Client.id,               # Incluir el ID del cliente
        Client.first_name,
        Client.last_name
    ).join(Client).order_by(Appointment.date_time).all()

    appointments_data = []
    # Asegurarse de desempaquetar todos los valores de la tupla de la consulta
    for appt_id, date_time, description, client_id, client_first_name, client_last_name in appointments:
        appointments_data.append({
            'id': appt_id,
            'title': f"{client_first_name} {client_last_name}: {description}",
            'start': date_time.isoformat(), # Formato ISO para JavaScript
            'date': date_time.strftime('%Y-%m-%d'), # Solo la fecha para fácil filtrado
            'time': date_time.strftime('%H:%M'), # Solo la hora
            'client_id': client_id, # Usar el ID del cliente correcto
            'client_name': f"{client_first_name} {client_last_name}",
            'description': description # Añadir la descripción del turno para uso directo
        })
    return jsonify(appointments_data)

