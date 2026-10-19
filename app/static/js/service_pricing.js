document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('service-form');
    if (!form) return;
    const initial = JSON.parse(document.getElementById('service-initial-data').textContent);
    const enabled = document.getElementById('pricing-enabled');
    const fields = document.getElementById('pricing-fields');
    const materials = document.getElementById('pricing-materials');
    const price = document.getElementById('price');
    const currency = value => new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(value);
    const round = value => Math.round((value + Number.EPSILON) * 100) / 100;
    const numeric = value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 1e9;
    let suggestion = null;
    function pricingData() {
        const data = { kind: document.getElementById('pricing-kind').value, length: document.getElementById('pricing-length').value };
        for (const key of ['labour', 'overhead', 'other_costs', 'margin']) data[key] = document.getElementById(`pricing-${key}`).value;
        data.materials = [...materials.children].map(row => ({
            ...Object.fromEntries([...row.querySelectorAll('[data-key]')].map(input => [input.dataset.key, input.type === 'checkbox' ? input.checked : input.value])),
            product_id: row.querySelector('[data-product]').value ? Number(row.querySelector('[data-product]').value) : null
        }));
        return data;
    }
    function recalculate() {
        const data = pricingData();
        let valid = ['labour', 'overhead', 'other_costs', 'margin'].every(key => numeric(data[key])) && Number(data.margin) < 100;
        let materialTotal = 0;
        data.materials.forEach((row, index) => {
            const costInput = materials.children[index].querySelector('[data-key="package_cost"]');
            if (row.client_supplied && row.package_cost === '') { row.package_cost = '0'; costInput.value = '0'; }
            costInput.readOnly = row.client_supplied;
            const good = row.label.trim() && ['package_cost', 'package_quantity', 'quantity'].every(key => numeric(row[key])) && Number(row.package_quantity) > 0 && Number(row.quantity) > 0;
            valid = valid && Boolean(good);
            const cost = good ? (row.client_supplied ? 0 : round(Number(row.package_cost) * Number(row.quantity) / Number(row.package_quantity))) : 0;
            materialTotal += cost;
            materials.children[index].querySelector('.material-cost').textContent = good ? currency(cost) : '\u2014';
        });
        const labour = round(Number(data.labour) || 0);
        const overhead = round(Number(data.overhead) || 0) + round(Number(data.other_costs) || 0);
        const total = round(materialTotal + labour + overhead);
        suggestion = valid ? round(total / (1 - Number(data.margin) / 100)) : null;
        document.getElementById('summary-materials').textContent = currency(materialTotal);
        document.getElementById('summary-labour').textContent = currency(labour);
        document.getElementById('summary-overhead').textContent = currency(overhead);
        document.getElementById('summary-total').textContent = valid ? currency(total) : '\u2014';
        document.getElementById('summary-price').textContent = suggestion === null ? '\u2014' : currency(suggestion);
        const charged = Number(price.value) || 0;
        document.getElementById('summary-profit').textContent = valid ? currency(charged - total) : '\u2014';
        document.getElementById('summary-margin').textContent = valid && charged > 0 ? `${((charged - total) / charged * 100).toFixed(2)} %` : '\u2014';
        document.getElementById('use-suggested-price').disabled = suggestion === null || suggestion > 1e9;
        const error = document.getElementById('pricing-error');
        error.hidden = valid;
        error.textContent = 'Completa los costos y cantidades. El margen debe ser menor al 100%.';
        document.getElementById('pricing-data').value = JSON.stringify(data);
    }
    function addMaterial(data = {}) {
        const row = document.getElementById('material-template').content.firstElementChild.cloneNode(true);
        const picker = row.querySelector('[data-product]');
        initial.products.forEach(product => picker.add(new Option(product.label, product.id)));
        picker.value = data.product_id || '';
        row.querySelectorAll('[data-key]').forEach(input => {
            const value = data[input.dataset.key];
            if (input.type === 'checkbox') input.checked = Boolean(value);
            else if (value !== undefined) input.value = value;
        });
        picker.addEventListener('change', () => {
            const product = initial.products.find(product => String(product.id) === picker.value);
            if (product) {
                row.querySelector('[data-key="label"]').value = product.label;
                row.querySelector('[data-key="package_cost"]').value = product.cost;
            }
            recalculate();
        });
        row.querySelector('.service-remove').addEventListener('click', () => { row.remove(); recalculate(); });
        materials.append(row);
        recalculate();
    }
    function addStockRow(data = {}) {
        const row = document.createElement('div'); row.className = 'service-stock-row';
        const productLabel = document.createElement('label'); productLabel.textContent = 'Producto';
        const select = document.createElement('select'); select.name = 'product_ids'; select.required = true;
        select.add(new Option('Seleccionar producto', ''));
        initial.products.forEach(product => select.add(new Option(`${product.label} (Stock: ${product.stock})`, product.id)));
        select.value = data.product_id || ''; productLabel.append(select);
        const quantityLabel = document.createElement('label'); quantityLabel.textContent = 'Envases';
        const quantity = document.createElement('input');
        quantity.type = 'number'; quantity.name = 'quantities_used'; quantity.min = '1'; quantity.step = '1'; quantity.required = true;
        quantity.value = data.quantity || 1; quantityLabel.append(quantity);
        const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'service-remove'; remove.textContent = '\u00d7';
        remove.title = 'Quitar producto'; remove.setAttribute('aria-label', 'Quitar producto'); remove.addEventListener('click', () => row.remove());
        row.append(productLabel, quantityLabel, remove); document.getElementById('used-products-container').append(row);
    }
    if (initial.pricing) {
        const data = initial.pricing;
        document.getElementById('pricing-kind').value = data.kind || 'raiz';
        document.getElementById('pricing-length').value = data.length || 'corto';
        for (const key of ['labour', 'overhead', 'other_costs', 'margin']) document.getElementById(`pricing-${key}`).value = data[key] ?? 0;
        if (Array.isArray(data.materials)) data.materials.filter(row => row && typeof row === 'object' && !Array.isArray(row)).forEach(addMaterial);
    }
    initial.associations.forEach(addStockRow);
    document.getElementById('add-material').addEventListener('click', () => addMaterial());
    document.getElementById('add-product-btn').addEventListener('click', () => addStockRow());
    enabled.addEventListener('change', () => {
        fields.hidden = fields.disabled = !enabled.checked;
        document.getElementById('pricing-summary').hidden = !enabled.checked;
        recalculate();
    });
    form.addEventListener('input', recalculate); form.addEventListener('change', recalculate);
    document.getElementById('use-suggested-price').addEventListener('click', () => { if (suggestion !== null) { price.value = suggestion.toFixed(2); recalculate(); } });
    form.addEventListener('submit', event => { recalculate(); if (enabled.checked && suggestion === null) { event.preventDefault(); document.getElementById('pricing-error').focus(); } });
    recalculate();
});
