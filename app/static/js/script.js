// Variable global para almacenar los productos del dropdown
let availableProducts = [];

/**
 * Fetches products from the API to populate the dropdown.
 * Fetches products from the API to populate the dropdown.
 * @returns {Promise<void>} A promise that resolves when products are fetched and stored.
 */
async function fetchProductsForDropdown() {
    try {
        const response = await fetch('/api/products_list');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        availableProducts = await response.json();
        console.log("Productos cargados:", availableProducts);
    } catch (error) {
        console.error("Error al cargar productos para el dropdown:", error);
        // Optionally display an error message to the user
        displayMessage('Error al cargar productos. Por favor, recarga la página.', 'danger');
    }
}

/**
 * Adds a new item row to the order form.
 */
function addItemToOrder() {
    const container = document.getElementById('order-items-container');
    const itemIndex = container.children.length; // Unique index for new item

    const itemDiv = document.createElement('div');
    itemDiv.className = 'bg-gray-50 p-4 rounded-lg shadow-inner border border-gray-200';
    itemDiv.innerHTML = `
        <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-semibold text-gray-700">Producto #${itemIndex + 1}</h3>
            <button type="button" class="text-red-500 hover:text-red-700 font-bold text-xl remove-item-btn" title="Eliminar este producto">
                &times;
            </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label for="product_select_${itemIndex}" class="block text-gray-700 text-sm font-bold mb-2">Seleccionar Producto:</label>
                <select id="product_select_${itemIndex}" 
                        name="product_id[]" 
                        class="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent product-select">
                    <option value="0">-- Seleccionar de inventario --</option>
                    ${availableProducts.map(p => `<option value="${p.id}">${p.description} (${p.brand})</option>`).join('')}
                </select>
                <p class="text-xs text-gray-500 mt-1">O rellena manualmente si no está en inventario</p>
            </div>
            <div>
                <label for="item_brand_${itemIndex}" class="block text-gray-700 text-sm font-bold mb-2">Marca:</label>
                <input type="text" id="item_brand_${itemIndex}" name="item_brand[]" required
                       class="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent item-brand">
            </div>
            <div>
                <label for="item_description_${itemIndex}" class="block text-gray-700 text-sm font-bold mb-2">Descripción:</label>
                <input type="text" id="item_description_${itemIndex}" name="item_description[]" required
                       class="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent item-description">
            </div>
            <div>
                <label for="item_wholesale_price_${itemIndex}" class="block text-gray-700 text-sm font-bold mb-2">Precio Mayorista ($):</label>
                <input type="number" step="0.01" id="item_wholesale_price_${itemIndex}" name="item_wholesale_price[]" required min="0"
                       class="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent item-wholesale-price">
            </div>
            <div>
                <label for="item_quantity_${itemIndex}" class="block text-gray-700 text-sm font-bold mb-2">Cantidad:</label>
                <input type="number" step="1" id="item_quantity_${itemIndex}" name="item_quantity[]" required min="1" value="1"
                       class="shadow-sm appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent item-quantity">
            </div>
            <div class="md:col-span-2 text-right pt-2">
                <span class="font-semibold text-lg text-gray-800">Subtotal: $<span class="item-subtotal">0.00</span></span>
            </div>
        </div>
    `;
    container.appendChild(itemDiv);

    // Add event listeners for the new elements
    const selectElement = itemDiv.querySelector(`.product-select`);
    const brandInput = itemDiv.querySelector(`.item-brand`);
    const descriptionInput = itemDiv.querySelector(`.item-description`);
    const wholesalePriceInput = itemDiv.querySelector(`.item-wholesale-price`);
    const quantityInput = itemDiv.querySelector(`.item-quantity`);
    const removeButton = itemDiv.querySelector('.remove-item-btn');

    selectElement.addEventListener('change', () => 
        populateProductDetails(selectElement, brandInput, descriptionInput, wholesalePriceInput)
    );
    wholesalePriceInput.addEventListener('input', calculateOrderTotal);
    quantityInput.addEventListener('input', calculateOrderTotal);
    
    // Initial calculation for the new item
    calculateOrderTotal();

    // Event listener for removing item
    removeButton.addEventListener('click', () => {
        itemDiv.remove();
        calculateOrderTotal(); // Recalculate total after removal
    });
}

/**
 * Populates brand, description, and wholesale price fields based on selected product.
 * @param {HTMLSelectElement} selectElement - The select element for product ID.
 * @param {HTMLInputElement} brandInput - The brand input field.
 * @param {HTMLInputElement} descriptionInput - The description input field.
 * @param {HTMLInputElement} wholesalePriceInput - The wholesale price input field.
 */
function populateProductDetails(selectElement, brandInput, descriptionInput, wholesalePriceInput) {
    const selectedProductId = selectElement.value;
    if (selectedProductId !== '0') {
        const selectedProduct = availableProducts.find(p => p.id == selectedProductId);
        if (selectedProduct) {
            brandInput.value = selectedProduct.brand;
            descriptionInput.value = selectedProduct.description;
            wholesalePriceInput.value = selectedProduct.wholesale_price;
            // Disable manual input after auto-completion, but allow if they change the select back
            brandInput.readOnly = true;
            descriptionInput.readOnly = true;
            wholesalePriceInput.readOnly = true;
        }
    } else {
        // If "Seleccionar de inventario" is chosen, clear fields and enable manual input
        brandInput.value = '';
        descriptionInput.value = '';
        wholesalePriceInput.value = '';
        brandInput.readOnly = false;
        descriptionInput.readOnly = false;
        wholesalePriceInput.readOnly = false;
    }
    calculateOrderTotal(); // Recalculate total after updating details
}

/**
 * Calculates the subtotal for each item and the grand total for the order.
 */
function calculateOrderTotal() {
    let grandTotal = 0;
    const orderItems = document.querySelectorAll('#order-items-container > div');

    orderItems.forEach(itemDiv => {
        const wholesalePriceInput = itemDiv.querySelector('.item-wholesale-price');
        const quantityInput = itemDiv.querySelector('.item-quantity');
        const subtotalSpan = itemDiv.querySelector('.item-subtotal');

        const wholesalePrice = parseFloat(wholesalePriceInput.value) || 0;
        const quantity = parseInt(quantityInput.value) || 0;

        const subtotal = wholesalePrice * quantity;
        subtotalSpan.textContent = subtotal.toFixed(2);
        grandTotal += subtotal;
    });

    document.getElementById('total-order-price').textContent = `$${grandTotal.toFixed(2)}`;
    document.getElementById('hidden-total-order-price').value = grandTotal.toFixed(2);
}

// Event listener for the "Add Product to Order" button
const addItemButton = document.getElementById('add-item-btn');
if (addItemButton) {
    addItemButton.addEventListener('click', addItemToOrder);
}


// --- Funciones para la exportación a PDF (requiere jsPDF) ---
// jsPDF CDN: https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js

// Cargar jsPDF dinámicamente si no está cargado
function loadJsPDF() {
    return new Promise((resolve, reject) => {
        if (typeof jspdf !== 'undefined') {
            resolve(jspdf);
            return;
        }
        const script = document.createElement('script');
        script.src = "https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js";
        script.onload = () => resolve(jspdf);
        script.onerror = () => reject(new Error("Failed to load jsPDF script."));
        document.head.appendChild(script);
    });
}

/**
 * Exports a specific order to a PDF document.
 * @param {number} orderId - The ID of the order to export.
 * @param {string} orderDate - The date of the order (YYYY-MM-DD format).
 */
async function exportOrderToPdf(orderId, orderDate) {
    try {
        const { jsPDF } = await loadJsPDF(); // Carga jsPDF
        const doc = new jsPDF();

        // Se cambió el selector para no usar :has()
        const tableBody = document.querySelector('#ordersTable tbody');
        let orderRow = null;
        if (tableBody) {
            for (const row of tableBody.rows) {
                const firstCell = row.cells[0]; // First cell contains the order ID
                if (firstCell && firstCell.textContent.trim() === String(orderId)) {
                    orderRow = row;
                    break;
                }
            }
        }
        
        if (!orderRow) {
            displayMessage('No se pudo encontrar el pedido en la tabla para exportar.', 'danger');
            return;
        }

        const orderDetails = {};
        // Extract order details from the row
        const cells = orderRow.querySelectorAll('td');
        if (cells.length > 0) {
            orderDetails.id = cells[0].textContent.trim();
            // orderDetails.date = cells[1].textContent.trim(); // Se elimina la fecha del pedido del PDF
            
            // Extract items
            const itemsListElement = cells[2].querySelector('ul');
            orderDetails.items = [];
            if (itemsListElement) {
                itemsListElement.querySelectorAll('li').forEach(li => {
                    orderDetails.items.push(li.textContent.trim());
                });
            }
            // orderDetails.total = cells[3].textContent.trim(); // Se elimina el total del pedido del PDF
        } else {
            displayMessage('No se pudieron extraer los detalles del pedido de la tabla.', 'danger');
            return;
        }

        // --- Encabezado del documento PDF ---
        doc.setFontSize(22);
        doc.text(`Detalle del Pedido #${orderDetails.id}`, 10, 20);
        // La línea de la fecha del pedido ha sido eliminada.
        // La línea del total del pedido ha sido eliminada.

        let y = 40; // Posición Y inicial para la tabla, ajustada al eliminar la fecha y el total
        const margin = 10;
        const columnWidths = {
            cantidad: 20,
            marca: 75, 
            descripcion: 95
        };

        // --- Dibujar encabezados de la tabla ---
        doc.setFontSize(12);
        doc.setFont(undefined, 'bold'); // Establecer negrita para los encabezados
        doc.text("Cantidad", margin, y);
        doc.text("Marca", margin + columnWidths.cantidad, y);
        doc.text("Descripción", margin + columnWidths.cantidad + columnWidths.marca, y);
        doc.setFont(undefined, 'normal'); // Restablecer a normal después de los encabezados

        y += 7; // Espacio entre el encabezado y la primera línea

        // Dibujar línea debajo de los encabezados
        doc.line(margin, y, doc.internal.pageSize.width - margin, y);
        y += 5; // Espacio después de la línea del encabezado

        // --- Dibujar filas de la tabla ---
        doc.setFontSize(10); // Tamaño de fuente para el contenido de la tabla
        orderDetails.items.forEach(itemText => {
            // Regex para parsear "1 x Marca - Descripción ($Price)"
            // El grupo del precio unitario se extrae pero no se usa para el PDF
            const parts = itemText.match(/(\d+)\s+x\s+(.*?)\s+-\s+(.*?)\s+\((.*?)\)/); 
            let quantity = '';
            let brand = '';
            let description = '';

            if (parts && parts.length === 5) {
                quantity = parts[1];
                brand = parts[2];
                description = parts[3];
            } else {
                // Fallback si el regex no coincide.
                description = itemText; 
            }

            // Dibuja el contenido de la fila
            doc.text(quantity, margin, y);
            doc.text(brand, margin + columnWidths.cantidad, y);
            doc.text(description, margin + columnWidths.cantidad + columnWidths.marca, y);
            
            y += 7; // Espacio entre filas
        });

        doc.save(`pedido_${orderDate}_${orderId}.pdf`);
        displayMessage('Pedido exportado a PDF exitosamente!', 'success');

    } catch (error) {
        console.error("Error al exportar a PDF:", error);
        displayMessage(`Error al exportar a PDF: ${error.message}`, 'danger');
    }
}

/**
 * Displays a flash-like message to the user.
 * @param {string} message - The message content.
 * @param {string} category - The category of the message ('success' or 'danger').
 */
function displayMessage(message, category) {
    const mainContainer = document.querySelector('main.container');
    if (!mainContainer) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `flash-message flash-${category} rounded-lg shadow-md mb-4`;
    messageDiv.setAttribute('role', 'alert');
    messageDiv.textContent = message;

    // Insert at the beginning of the main content area
    mainContainer.prepend(messageDiv);

    // Automatically remove message after a few seconds
    setTimeout(() => {
        messageDiv.remove();
    }, 5000); // 5 seconds
}
