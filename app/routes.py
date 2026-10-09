from flask import render_template, request, redirect, url_for, flash, jsonify, session
from app import app, db
from app.models import Product, Order, OrderItem, Client, ClientImage, Appointment, Service, UsedProduct
from app.google_calendar import (
    build_google_flow,
    delete_appointment_from_google,
    delete_google_token,
    google_calendar_configured,
    google_calendar_connected,
    google_event_start,
    list_google_events,
    get_google_event,
    save_credentials,
    sync_appointment_to_google,
)
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func, extract
from werkzeug.utils import secure_filename
import locale
import os
from uuid import uuid4


CLIENT_EVALUATION_OPTIONS = {
    'hair_types': ['Virgen', 'Procesado', 'Fino', 'Normal', 'Ondulado', 'Rizado'],
    'textures': ['Grueso', 'Normal', 'Fino'],
    'scalp_conditions': ['Nada', 'Poco', 'Muy'],
    'scalp_properties': ['Seborrea', 'Pitiriasis', 'Alopecia', 'Pediculosis'],
}

ALLOWED_CLIENT_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _client_images_dir():
    upload_dir = os.path.join(app.static_folder, 'uploads', 'client_images')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _allowed_client_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_CLIENT_IMAGE_EXTENSIONS


def _delete_client_image_file(filename):
    if not filename:
        return
    image_path = os.path.join(_client_images_dir(), filename)
    if os.path.exists(image_path):
        os.remove(image_path)


def _serialize_selected(values):
    return ','.join(value for value in values if value)


def _selected_values(value):
    if not value:
        return []
    return [item for item in value.split(',') if item]


def _appointment_minutes():
    try:
        return max(1, int(os.environ.get('GOOGLE_CALENDAR_EVENT_MINUTES', '60')))
    except ValueError:
        return 60


def _appointment_conflict(proposed_time, exclude_id=None):
    # Use the same fixed duration as Google Calendar until services have durations.
    duration = timedelta(minutes=_appointment_minutes())
    query = Appointment.query.filter(
        Appointment.date_time > proposed_time - duration,
        Appointment.date_time < proposed_time + duration,
    )
    if exclude_id is not None:
        query = query.filter(Appointment.id != exclude_id)
    return query.first() is not None


def _apply_client_form_data(client):
    client.first_name = request.form['first_name']
    client.last_name = request.form['last_name']
    client.address = request.form.get('address')
    client.phone = request.form.get('phone')
    client.evaluation_hair_types = _serialize_selected(request.form.getlist('evaluation_hair_types'))
    client.evaluation_textures = _serialize_selected(request.form.getlist('evaluation_textures'))
    client.evaluation_scalp_conditions = _serialize_selected(request.form.getlist('evaluation_scalp_conditions'))
    client.evaluation_scalp_properties = _serialize_selected(request.form.getlist('evaluation_scalp_properties'))
    client.evaluation_hair_loss = 'Alopecia' in request.form.getlist('evaluation_scalp_properties')
    client.evaluation_dandruff = 'Pitiriasis' in request.form.getlist('evaluation_scalp_properties')
    client.evaluation_allergy_has = request.form.get('evaluation_allergy_has') == 'yes'
    client.evaluation_allergy_detail = request.form.get('evaluation_allergy_detail')
    client.evaluation_natural_tone = request.form.get('evaluation_natural_tone')
    client.evaluation_artificial_tone = request.form.get('evaluation_artificial_tone')
    client.evaluation_gray_percentage = request.form.get('evaluation_gray_percentage')
    client.evaluation_growth = request.form.get('evaluation_growth')
    client.evaluation_desired_tone = request.form.get('evaluation_desired_tone')
    client.evaluation_product_to_use = request.form.get('evaluation_product_to_use')
    client.evaluation_application_exposure = request.form.get('evaluation_application_exposure')
    client.evaluation_notes = request.form.get('evaluation_notes')

    for index in range(1, 6):
        setattr(client, f'evaluation_formula_has_{index}', request.form.get(f'evaluation_formula_has_{index}'))
        setattr(client, f'evaluation_formula_wants_{index}', request.form.get(f'evaluation_formula_wants_{index}'))

    for index in range(1, 5):
        setattr(client, f'evaluation_formula_text_{index}', request.form.get(f'evaluation_formula_text_{index}'))


@app.route('/')
def index():
    """
    Panel de la jornada de trabajo.
    """
    today = date.today()

    today_appointments = Appointment.query.join(Client).filter(
        func.date(Appointment.date_time) == today
    ).order_by(Appointment.date_time).all()

    formatted_today_appointments = []
    for appt in today_appointments:
        formatted_today_appointments.append({
            'time': appt.date_time.strftime('%H:%M'),
            'client_name': f"{appt.client.first_name} {appt.client.last_name}",
            'description': appt.description,
            'client_id': appt.client.id,
            'appointment_id': appt.id
        })

    return render_template(
        'dashboard.html',
        title='Inicio',
        today_formatted=today.strftime('%A, %d de %B'),
        today_appointments=formatted_today_appointments,
        client_count=Client.query.count(),
        product_count=Product.query.count(),
        appointment_count=len(formatted_today_appointments),
        low_stock_count=Product.query.filter(Product.stock <= 3).count()
    )

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
                           today_formatted_date=today_formatted)

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
    total_units = 0
    total_items = 0
    for order in orders:
        order.items_list = OrderItem.query.filter_by(order_id=order.id).all()
        total_items += len(order.items_list)
        total_units += sum(item.quantity for item in order.items_list)

    total_orders_amount = sum(order.total_order_price for order in orders)

    return render_template('orders.html', 
                           orders=orders, 
                           from_date=search_from_date, 
                           to_date=search_to_date,
                           total_items=total_items,
                           total_units=total_units,
                           total_orders_amount=total_orders_amount)


@app.route('/orders/add', methods=['GET', 'POST'])
def add_order():
    """
    Permite agregar un nuevo pedido y actualiza el stock de productos.
    """
    products_for_dropdown = Product.query.all()

    if request.method == 'POST':
        order_date_str = request.form['order_date']
        try:
            order_date = datetime.strptime(order_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Formato de fecha inválido. Por favor, usa AAAA-MM-DD.', 'danger')
            return render_template('add_order.html', products=products_for_dropdown)

        new_order = Order(order_date=order_date, total_order_price=0.0)
        db.session.add(new_order)
        db.session.flush()

        item_product_ids = request.form.getlist('product_id[]')
        item_brands = request.form.getlist('item_brand[]')
        item_descriptions = request.form.getlist('item_description[]')
        item_wholesale_prices = request.form.getlist('item_wholesale_price[]')
        item_quantities = request.form.getlist('item_quantity[]')

        total_order_price = 0.0
        
        try:
            for i in range(len(item_brands)):
                product_id_val = int(item_product_ids[i]) if item_product_ids[i] and item_product_ids[i] != '0' else None
                wholesale_price_at_order = float(item_wholesale_prices[i])
                quantity = int(item_quantities[i])

                if quantity <= 0:
                    raise ValueError(f'La cantidad para el producto "{item_descriptions[i]}" debe ser mayor que cero.')

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

                # Incrementar el stock del producto si existe
                if product_id_val:
                    product = Product.query.get(product_id_val)
                    if product:
                        product.stock += quantity
            
            new_order.total_order_price = total_order_price
            db.session.commit()
            flash('Pedido agregado y stock actualizado exitosamente!', 'success')
            return redirect(url_for('orders'))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
            return render_template('add_order.html', products=products_for_dropdown)
        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar el pedido: {e}', 'danger')
            return render_template('add_order.html', products=products_for_dropdown)

    return render_template('add_order.html', products=products_for_dropdown)


# --- API Endpoints ---

@app.route('/api/products_list')
def products_list_api():
    """
    API endpoint para obtener la lista de productos (ID y descripción) para el dropdown.
    """
    # Se modificó para incluir 'brand', 'wholesale_price' y 'stock'
    products = Product.query.with_entities(Product.id, Product.description, Product.brand, Product.wholesale_price, Product.stock).all()
    # Retorna una lista de diccionarios, útil para JavaScript
    return jsonify([{'id': p.id, 'description': p.description, 'brand': p.brand, 'wholesale_price': p.wholesale_price, 'stock': p.stock} for p in products])

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

@app.route('/api/clients_list')
def clients_list_api():
    """
    API endpoint para obtener la lista de clientes (ID, nombre, apellido) para el dropdown.
    """
    clients = Client.query.with_entities(Client.id, Client.first_name, Client.last_name).order_by(Client.first_name).all()
    return jsonify([{'id': c.id, 'name': f"{c.first_name} {c.last_name}"} for c in clients])


# --- Rutas de Gestión de Clientes ---

@app.route('/clients')
def clients():
    """
    Muestra la lista de clientes.
    """
    clients = Client.query.order_by(Client.first_name, Client.last_name).all()
    return render_template('clients.html', clients=clients)

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    """
    Permite agregar un nuevo cliente.
    """
    if request.method == 'POST':
        new_client = Client()
        _apply_client_form_data(new_client)
        try:
            db.session.add(new_client)
            db.session.commit()
            flash('Cliente agregado exitosamente!', 'success')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Error al agregar cliente: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_client.html',
                           client=None,
                           title='Agregar Cliente',
                           evaluation_options=CLIENT_EVALUATION_OPTIONS,
                           selected_values=_selected_values)

@app.route('/clients/edit/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    """
    Permite editar un cliente existente.
    """
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        _apply_client_form_data(client)
        try:
            db.session.commit()
            flash('Cliente actualizado exitosamente!', 'success')
            return redirect(url_for('clients'))
        except Exception as e:
            flash(f'Error al actualizar cliente: {e}', 'danger')
            db.session.rollback()
    return render_template('add_edit_client.html',
                           client=client,
                           title='Editar Cliente',
                           evaluation_options=CLIENT_EVALUATION_OPTIONS,
                           selected_values=_selected_values)

@app.route('/clients/delete/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    """
    Permite eliminar un cliente.
    """
    client = Client.query.get_or_404(client_id)
    try:
        for image in client.images:
            _delete_client_image_file(image.filename)
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
    return render_template('client_detail.html',
                           client=client,
                           title=f'Detalle de {client.first_name} {client.last_name}',
                           evaluation_options=CLIENT_EVALUATION_OPTIONS,
                           selected_values=_selected_values)


@app.route('/clients/<int:client_id>/images/add', methods=['POST'])
def add_client_image(client_id):
    """
    Permite subir una o varias imagenes para un cliente.
    """
    client = Client.query.get_or_404(client_id)
    files = request.files.getlist('images')
    saved_count = 0

    try:
        for image_file in files:
            if not image_file or not image_file.filename:
                continue

            if not _allowed_client_image(image_file.filename):
                flash(f'Formato no permitido para "{image_file.filename}". Usa PNG, JPG, JPEG, GIF o WEBP.', 'danger')
                continue

            original_filename = secure_filename(image_file.filename)
            extension = original_filename.rsplit('.', 1)[1].lower()
            filename = f'client_{client.id}_{uuid4().hex}.{extension}'
            image_file.save(os.path.join(_client_images_dir(), filename))

            client_image = ClientImage(
                client_id=client.id,
                filename=filename,
                original_filename=original_filename
            )
            db.session.add(client_image)
            saved_count += 1

        if saved_count:
            db.session.commit()
            flash(f'{saved_count} imagen(es) subida(s) correctamente.', 'success')
        else:
            db.session.rollback()
            flash('No se seleccionaron imagenes validas para subir.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al subir imagenes: {e}', 'danger')

    return redirect(url_for('client_detail', client_id=client.id))


@app.route('/clients/<int:client_id>/images/delete/<int:image_id>', methods=['POST'])
def delete_client_image(client_id, image_id):
    """
    Elimina una imagen asociada a un cliente.
    """
    client = Client.query.get_or_404(client_id)
    image = ClientImage.query.get_or_404(image_id)

    if image.client_id != client.id:
        flash('Imagen no encontrada para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))

    try:
        _delete_client_image_file(image.filename)
        db.session.delete(image)
        db.session.commit()
        flash('Imagen eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar imagen: {e}', 'danger')

    return redirect(url_for('client_detail', client_id=client.id))

# --- Rutas de Gestión de Turnos (Appointments) ---

# Modificado para aceptar prefill_date y prefill_time
@app.route('/clients/<int:client_id>/appointments/add', methods=['GET', 'POST'])
@app.route('/appointments/add', methods=['GET', 'POST']) # Nueva ruta para agregar desde el calendario
def add_appointment(client_id=None): # <--- CORRECCIÓN CLAVE AQUÍ: client_id es un argumento opcional
    """
    Permite agregar un nuevo turno.
    Puede recibir client_id, prefill_date y prefill_time como parámetros de URL o como parte de la ruta.
    """
    # Si client_id viene de la URL (ruta /clients/<int:client_id>/appointments/add)
    # y no es None (cuando viene de /appointments/add), usarlo.
    # Si viene del request.args (cuando se llama desde el calendario con un parámetro de consulta),
    # prevalece o se usa si el de la URL es None.
    
    # Prioridad: 1. Argumento de la URL (si existe), 2. Parámetro de consulta 'client_id'
    if client_id is None: # Si no vino en la ruta, intenta buscarlo en los parámetros de consulta
        client_id = request.args.get('client_id', type=int)

    prefill_date = request.args.get('date')
    prefill_time = request.args.get('time')

    client = None
    if client_id: # Ahora, si client_id tiene un valor (ya sea de la URL o del query param)
        client = Client.query.get_or_404(client_id)

    if request.method == 'POST':
        # Si el turno se agrega desde el formulario del calendario, el client_id podría venir en el form data
        # O si el campo de selección de cliente permite elegir otro cliente, su ID también vendrá aquí.
        form_client_id = request.form.get('client_id', type=int)
        if form_client_id:
            client = Client.query.get_or_404(form_client_id)
        
        if not client:
            flash('Cliente no seleccionado para el turno.', 'danger')
            # Si no hay cliente, redirigir a la página de clientes o mostrar error
            clients_for_dropdown = Client.query.order_by(Client.first_name).all()
            return render_template('add_edit_appointment.html', 
                                   client=None, 
                                   appointment=None, 
                                   title='Agregar Turno',
                                   clients_for_dropdown=clients_for_dropdown,
                                   prefill_date=prefill_date,
                                   prefill_time=prefill_time)


        date_time_str = request.form['date_time']
        description = request.form['description']
        try:
            date_time_obj = datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
            if _appointment_conflict(date_time_obj):
                flash('Ya hay un turno en ese horario. Selecciona otro horario.', 'danger')
                return redirect(url_for('add_appointment', client_id=client.id, date=date_time_obj.strftime('%Y-%m-%d'), time=date_time_obj.strftime('%H:%M')))
            
            new_appointment = Appointment(client_id=client.id, date_time=date_time_obj, description=description)
            db.session.add(new_appointment)
            db.session.flush()
            if google_calendar_connected():
                try:
                    new_appointment.google_event_id = sync_appointment_to_google(new_appointment)
                except Exception as sync_error:
                    flash(f'Turno guardado, pero no se pudo sincronizar con Google Calendar: {sync_error}', 'danger')
            db.session.commit()
            flash('Turno agregado exitosamente!', 'success')
            # Redirigir al detalle del cliente si se agregó desde allí, o al calendario si se agregó desde el calendario
            if request.referrer and 'calendar' in request.referrer:
                return redirect(url_for('appointments_calendar'))
            elif client:
                return redirect(url_for('client_detail', client_id=client.id))
            else:
                return redirect(url_for('appointments_calendar')) # Fallback
        except ValueError:
            flash('Formato de fecha y/o hora inválido. Usa AAAA-MM-DDTHH:MM.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'Error al agregar turno: {e}', 'danger')
            db.session.rollback()
    
    # Para GET requests
    clients_for_dropdown = Client.query.order_by(Client.first_name).all()
    return render_template('add_edit_appointment.html', 
                           client=client, # Pasa el objeto client al template si existe
                           appointment=None, 
                           title='Agregar Turno',
                           clients_for_dropdown=clients_for_dropdown,
                           prefill_date=prefill_date,
                           prefill_time=prefill_time)


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
        try:
            proposed_time = datetime.strptime(request.form['date_time'], '%Y-%m-%dT%H:%M')
            if _appointment_conflict(proposed_time, appointment.id):
                flash('Ya hay un turno en ese horario. Selecciona otro horario.', 'danger')
                return redirect(url_for('edit_appointment', client_id=client.id, appointment_id=appointment.id))
            appointment.date_time = proposed_time
            appointment.description = request.form['description']
            if google_calendar_connected():
                try:
                    appointment.google_event_id = sync_appointment_to_google(appointment)
                except Exception as sync_error:
                    flash(f'Turno actualizado, pero no se pudo sincronizar con Google Calendar: {sync_error}', 'danger')
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
        google_event_id = appointment.google_event_id
        db.session.delete(appointment)
        db.session.commit()
        if google_calendar_connected() and google_event_id:
            try:
                delete_appointment_from_google(google_event_id)
            except Exception as sync_error:
                flash(f'Turno eliminado, pero no se pudo eliminar de Google Calendar: {sync_error}', 'danger')
        flash('Turno eliminado exitosamente!', 'success')
    except Exception as e:
        flash(f'Error al eliminar turno: {e}', 'danger')
        db.session.rollback()
    return redirect(url_for('client_detail', client_id=client.id))

# --- Rutas de Gestión de Trabajos (Services) ---

@app.route('/clients/<int:client_id>/services/add', methods=['GET', 'POST'])
def add_service(client_id):
    """
    Permite agregar un nuevo trabajo/servicio y descuenta los productos usados del stock.
    """
    client = Client.query.get_or_404(client_id)

    if request.method == 'POST':
        date_str = request.form['date']
        description = request.form['description']
        product_ids = request.form.getlist('product_ids')
        quantities_used = request.form.getlist('quantities_used')

        try:
            price = float(request.form['price'])
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            new_service = Service(client_id=client.id, date=date_obj, description=description, price=price)
            
            # Procesar productos y stock
            for i, product_id in enumerate(product_ids):
                if not product_id or not quantities_used[i]:
                    continue
                
                product = Product.query.get(int(product_id))
                quantity = int(quantities_used[i])

                if not product or quantity <= 0:
                    raise ValueError("Producto o cantidad inválida.")

                if product.stock < quantity:
                    raise ValueError(f'No hay stock suficiente para "{product.description}". Stock actual: {product.stock}')

                # Descontar stock
                product.stock -= quantity

                # Crear la asociación
                used_product = UsedProduct(quantity=quantity)
                used_product.product = product
                new_service.product_associations.append(used_product)

            db.session.add(new_service)
            db.session.commit()
            flash('Trabajo/Servicio agregado y stock actualizado exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al agregar trabajo/servicio: {e}', 'danger')
            
    return render_template('add_edit_service.html', 
                           client=client, 
                           service=None, 
                           title=f'Agregar Trabajo para {client.first_name}')

@app.route('/clients/<int:client_id>/services/edit/<int:service_id>', methods=['GET', 'POST'])
def edit_service(client_id, service_id):
    """
    Permite editar un trabajo/servicio existente y actualiza el stock de productos.
    """
    client = Client.query.get_or_404(client_id)
    service = Service.query.get_or_404(service_id)

    if service.client_id != client_id:
        flash('Trabajo/Servicio no encontrado para este cliente.', 'danger')
        return redirect(url_for('client_detail', client_id=client.id))

    if request.method == 'POST':
        try:
            # Revertir el stock de los productos anteriormente asociados
            for assoc in service.product_associations:
                assoc.product.stock += assoc.quantity
            
            # Limpiar las asociaciones viejas
            service.product_associations.clear()

            # Actualizar datos del servicio
            service.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            service.description = request.form['description']
            service.price = float(request.form['price'])

            # Procesar nuevos productos y stock
            product_ids = request.form.getlist('product_ids')
            quantities_used = request.form.getlist('quantities_used')

            for i, product_id in enumerate(product_ids):
                if not product_id or not quantities_used[i]:
                    continue
                
                product = Product.query.get(int(product_id))
                quantity = int(quantities_used[i])

                if not product or quantity <= 0:
                    raise ValueError("Producto o cantidad inválida.")

                if product.stock < quantity:
                    raise ValueError(f'No hay stock suficiente para "{product.description}". Stock actual: {product.stock}')

                product.stock -= quantity
                
                used_product = UsedProduct(quantity=quantity)
                used_product.product = product
                service.product_associations.append(used_product)

            db.session.commit()
            flash('Trabajo/Servicio actualizado y stock corregido exitosamente!', 'success')
            return redirect(url_for('client_detail', client_id=client.id))

        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar trabajo/servicio: {e}', 'danger')

    return render_template('add_edit_service.html', 
                           client=client, 
                           service=service, 
                           title=f'Editar Trabajo para {client.first_name}')

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
    return render_template(
        'appointments_calendar.html',
        title='Calendario de Turnos',
        google_calendar_configured=google_calendar_configured(),
        google_calendar_connected=google_calendar_connected()
    )


@app.route('/google-calendar/connect')
def google_calendar_connect():
    """
    Inicia el flujo OAuth para conectar Google Calendar.
    """
    if not google_calendar_configured():
        flash('Faltan GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en la configuracion del servidor.', 'danger')
        return redirect(url_for('appointments_calendar'))

    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI') or url_for('google_calendar_callback', _external=True)
    flow = build_google_flow(redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['google_oauth_state'] = state
    return redirect(authorization_url)


@app.route('/google-calendar/callback')
def google_calendar_callback():
    """
    Recibe el callback de Google y guarda el token OAuth.
    """
    if not google_calendar_configured():
        flash('Faltan credenciales de Google Calendar en el servidor.', 'danger')
        return redirect(url_for('appointments_calendar'))

    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI') or url_for('google_calendar_callback', _external=True)
    flow = build_google_flow(redirect_uri)
    flow.state = session.get('google_oauth_state')
    authorization_response = request.url
    if redirect_uri.startswith('https://') and authorization_response.startswith('http://'):
        authorization_response = authorization_response.replace('http://', 'https://', 1)

    try:
        flow.fetch_token(authorization_response=authorization_response)
        save_credentials(flow.credentials)
        flash('Google Calendar conectado correctamente.', 'success')
    except Exception as e:
        flash(f'No se pudo conectar Google Calendar: {e}', 'danger')

    return redirect(url_for('appointments_calendar'))


@app.route('/google-calendar/disconnect', methods=['POST'])
def google_calendar_disconnect():
    """
    Desconecta Google Calendar eliminando el token local.
    """
    delete_google_token()
    flash('Google Calendar desconectado.', 'success')
    return redirect(url_for('appointments_calendar'))


@app.route('/google-calendar/sync', methods=['POST'])
def google_calendar_sync():
    """
    Sincroniza los turnos existentes con Google Calendar.
    """
    if not google_calendar_connected():
        flash('Primero conecta Google Calendar.', 'danger')
        return redirect(url_for('appointments_calendar'))

    synced = 0
    failed = 0
    appointments = Appointment.query.join(Client).order_by(Appointment.date_time).all()
    for appointment in appointments:
        try:
            appointment.google_event_id = sync_appointment_to_google(appointment)
            synced += 1
        except Exception:
            failed += 1

    db.session.commit()
    if failed:
        flash(f'Se sincronizaron {synced} turnos. {failed} no pudieron sincronizarse.', 'danger')
    else:
        flash(f'Se sincronizaron {synced} turnos con Google Calendar.', 'success')
    return redirect(url_for('appointments_calendar'))

@app.route('/google-calendar/import', methods=['GET', 'POST'])
def google_calendar_import():
    if not google_calendar_connected():
        flash('Primero conecta Google Calendar.', 'danger')
        return redirect(url_for('appointments_calendar'))
    today = date.today()
    values = request.form if request.method == 'POST' else request.args
    try:
        start_date = date.fromisoformat(values.get('from_date', today.replace(day=1).isoformat()))
        end_date = date.fromisoformat(values.get('to_date', (today + timedelta(days=30)).isoformat()))
        if end_date < start_date or (end_date - start_date).days > 366:
            raise ValueError
    except ValueError:
        flash('Selecciona un periodo valido de hasta un a\u00f1o.', 'danger')
        return redirect(url_for('google_calendar_import'))

    if request.method == 'POST':
        selected = list(dict.fromkeys(request.form.getlist('event_id')))
        if not selected or len(selected) > 250:
            flash('Selecciona entre 1 y 250 eventos.', 'warning')
        else:
            imported = 0
            skipped = 0
            for event_id in selected:
                if Appointment.query.filter_by(google_event_id=event_id).first():
                    skipped += 1
                    continue
                try:
                    client_id = int(request.form.get(f'client_{event_id}', ''))
                    if not db.session.get(Client, client_id):
                        raise ValueError
                    event = get_google_event(event_id)
                    if event.get('status') == 'cancelled':
                        raise ValueError
                    start = google_event_start(event, request.form.get(f'time_{event_id}'))
                    if not start or not start_date <= start.date() <= end_date:
                        raise ValueError
                    if _appointment_conflict(start):
                        flash(f"Horario ocupado: {event.get('summary', 'Evento')}.", 'warning')
                        skipped += 1
                        continue
                    db.session.add(Appointment(
                        client_id=client_id, date_time=start,
                        description=(event.get('summary') or 'Turno de Google Calendar')[:255],
                        google_event_id=event_id,
                    ))
                    db.session.flush()
                    imported += 1
                except (ValueError, TypeError, KeyError):
                    skipped += 1
                    flash('Un evento no tiene cliente, fecha u hora validos.', 'warning')
                except Exception:
                    db.session.rollback()
                    flash('No se pudo completar la importacion. Intenta nuevamente.', 'danger')
                    return redirect(url_for('google_calendar_import', from_date=start_date, to_date=end_date))
            db.session.commit()
            flash(f'Se importaron {imported} turnos. Se omitieron {skipped} eventos ya vinculados o no validos.', 'success' if imported else 'warning')
            return redirect(url_for('google_calendar_import', from_date=start_date, to_date=end_date))

    events = []
    try:
        for event in list_google_events(start_date, end_date):
            start = google_event_start(event)
            events.append({
                'id': event['id'], 'summary': event.get('summary') or 'Sin titulo',
                'date': start.strftime('%d/%m/%Y') if start else event['start']['date'],
                'time': start.strftime('%H:%M') if start else None,
            })
    except Exception:
        flash('No se pudieron consultar los eventos de Google Calendar. Revisa la conexion.', 'danger')
    linked = {appointment.google_event_id for appointment in Appointment.query.filter(Appointment.google_event_id.isnot(None)).all()}
    return render_template('google_calendar_import.html', title='Importar desde Google',
                           events=events, linked=linked, start_date=start_date, end_date=end_date,
                           clients=Client.query.order_by(Client.first_name, Client.last_name).all())


@app.route('/api/appointments')
def api_appointments():
    """
    API endpoint para obtener todos los turnos.
    Retorna una lista de diccionarios con los detalles de cada turno.
    """
    appointments = db.session.query(
        Appointment.id,
        Appointment.date_time,
        Appointment.description,
        Client.id,
        Client.first_name,
        Client.last_name
    ).join(Client).order_by(Appointment.date_time).all()

    appointments_data = []
    for appt_id, date_time, description, client_id, client_first_name, client_last_name in appointments:
        appointments_data.append({
            'id': appt_id,
            'title': f"{client_first_name} {client_last_name}: {description}",
            'start': date_time.isoformat(),
            'end': (date_time + timedelta(minutes=_appointment_minutes())).isoformat(),
            'date': date_time.strftime('%Y-%m-%d'),
            'time': date_time.strftime('%H:%M'),
            'client_id': client_id,
            'client_name': f"{client_first_name} {client_last_name}",
            'description': description,
            'url': url_for('edit_appointment', client_id=client_id, appointment_id=appt_id),
            'reschedule_url': url_for('reschedule_appointment', appointment_id=appt_id),
        })
    return jsonify(appointments_data)


@app.route('/api/appointments/<int:appointment_id>/reschedule', methods=['POST'])
def reschedule_appointment(appointment_id):
    appointment = db.get_or_404(Appointment, appointment_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Datos de turno invalidos.'), 400
    try:
        proposed_time = datetime.strptime(data.get('date_time', ''), '%Y-%m-%dT%H:%M')
    except (ValueError, TypeError):
        return jsonify(error='Fecha u hora invalida.'), 400
    if _appointment_conflict(proposed_time, appointment.id):
        return jsonify(error='Ya hay un turno en ese horario.'), 409
    appointment.date_time = proposed_time
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(error='No se pudo guardar el nuevo horario.'), 500
    warning = None
    if google_calendar_connected():
        try:
            appointment.google_event_id = sync_appointment_to_google(appointment)
            db.session.commit()
        except Exception:
            db.session.rollback()
            warning = 'Turno reprogramado. No se pudo sincronizar con Google Calendar.'
    return jsonify(success=True, warning=warning)

# --- Ruta para Reportes ---
@app.route('/reports')
def reports():
    """
    Muestra un reporte de ganancias y costos, con filtros por mes y año.
    """
    selected_month = request.args.get('month', type=int, default=datetime.utcnow().month)
    selected_year = request.args.get('year', type=int, default=datetime.utcnow().year)

    # --- Calcular Ingresos (de Servicios) ---
    services_query = Service.query
    if selected_year:
        services_query = services_query.filter(extract('year', Service.date) == selected_year)
    if selected_month:
        services_query = services_query.filter(extract('month', Service.date) == selected_month)
    
    total_revenue = services_query.with_entities(func.sum(Service.price)).scalar() or 0.0

    # --- Calcular Costos (de Pedidos) ---
    orders_query = Order.query
    if selected_year:
        orders_query = orders_query.filter(extract('year', Order.order_date) == selected_year)
    if selected_month:
        orders_query = orders_query.filter(extract('month', Order.order_date) == selected_month)

    total_cost = orders_query.with_entities(func.sum(Order.total_order_price)).scalar() or 0.0

    # --- Calcular Ganancia ---
    net_profit = total_revenue - total_cost

    # --- Datos para los filtros ---
    available_years_services = db.session.query(extract('year', Service.date)).distinct()
    available_years_orders = db.session.query(extract('year', Order.order_date)).distinct()
    
    all_years_query = available_years_services.union(available_years_orders)
    available_years = [y[0] for y in all_years_query.all() if y[0] is not None]
    available_years.sort(reverse=True)

    month_names = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
        7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }

    return render_template('reports.html',
                           title='Reporte de Ganancias',
                           total_revenue=total_revenue,
                           total_cost=total_cost,
                           net_profit=net_profit,
                           available_years=available_years,
                           month_names=month_names,
                           selected_year=selected_year,
                           selected_month=selected_month)
