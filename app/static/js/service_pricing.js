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
    let pricingValid = false;
    let activeExampleKey = typeof initial.pricing?.example_key === 'string' ? initial.pricing.example_key : null;
    let activeTemplateId = initial.pricing?.template_id || null;
    let pendingRefresh = null;
    function pricingData() {
        const data = { kind: document.getElementById('pricing-kind').value, length: document.getElementById('pricing-length').value };
        data.costs_confirmed = document.getElementById('pricing-costs-confirmed').checked;
        const reference = document.getElementById('pricing-reference-price').value;
        if (reference !== '') data.reference_price = reference;
        if (activeExampleKey) data.example_key = activeExampleKey;
        if (activeTemplateId && !initial.template_mode) data.template_id = activeTemplateId;
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
        if (data.reference_price !== undefined) valid = valid && numeric(data.reference_price);
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
        pricingValid = valid;
        const confirmed = data.costs_confirmed;
        suggestion = valid && confirmed ? round(total / (1 - Number(data.margin) / 100)) : null;
        document.getElementById('summary-materials').textContent = currency(materialTotal);
        document.getElementById('summary-labour').textContent = currency(labour);
        document.getElementById('summary-overhead').textContent = currency(overhead);
        document.getElementById('summary-total').textContent = valid && confirmed ? currency(total) : (confirmed ? '\u2014' : 'Sin verificar');
        document.getElementById('summary-price').textContent = suggestion === null ? '\u2014' : currency(suggestion);
        const charged = Number(price.value) || 0;
        document.getElementById('summary-profit').textContent = valid && confirmed && price.value !== '' ? currency(charged - total) : '\u2014';
        document.getElementById('summary-margin').textContent = valid && confirmed && charged > 0 ? `${((charged - total) / charged * 100).toFixed(2)} %` : '\u2014';
        const hasReference = data.reference_price !== undefined && numeric(data.reference_price);
        document.getElementById('summary-reference-row').hidden = !hasReference;
        document.getElementById('summary-reference').textContent = hasReference ? currency(Number(data.reference_price)) : '';
        const referenceButton = document.getElementById('use-reference-price');
        if (referenceButton) referenceButton.hidden = !hasReference;
        document.getElementById('pricing-reference-origin').hidden = !activeExampleKey?.startsWith('bucles-color-20261102-');
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
        if (data.product_id && !initial.products.some(product => product.id === data.product_id)) picker.add(new Option(`Producto no disponible: ${data.label}`, data.product_id));
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
    function applyPricing(data) {
        activeTemplateId = data.template_id || null;
        activeExampleKey = typeof data.example_key === 'string' ? data.example_key : null;
        document.getElementById('pricing-reference-price').value = data.reference_price ?? '';
        document.getElementById('pricing-costs-confirmed').checked = data.costs_confirmed !== false;
        materials.replaceChildren();
        document.getElementById('pricing-kind').value = data.kind || 'raiz';
        document.getElementById('pricing-length').value = data.length || 'corto';
        for (const key of ['labour', 'overhead', 'other_costs', 'margin']) document.getElementById(`pricing-${key}`).value = data[key] ?? 0;
        if (Array.isArray(data.materials)) data.materials.filter(row => row && typeof row === 'object' && !Array.isArray(row)).forEach(addMaterial);
        enabled.checked = true;
        fields.hidden = fields.disabled = false;
        document.getElementById('pricing-summary').hidden = false;
        recalculate();
    }
    if (initial.pricing) applyPricing(initial.pricing);
    initial.associations.forEach(addStockRow);
    document.getElementById('add-material').addEventListener('click', () => addMaterial());
    document.getElementById('add-product-btn')?.addEventListener('click', () => addStockRow());
    enabled.addEventListener('change', () => {
        fields.hidden = fields.disabled = !enabled.checked;
        document.getElementById('pricing-summary').hidden = !enabled.checked;
        recalculate();
    });
    form.addEventListener('input', recalculate); form.addEventListener('change', recalculate);
    document.getElementById('use-suggested-price').addEventListener('click', () => { if (suggestion !== null) { price.value = suggestion.toFixed(2); recalculate(); } });
    form.addEventListener('submit', event => { recalculate(); if (enabled.checked && !pricingValid) { event.preventDefault(); document.getElementById('pricing-error').focus(); } });
    document.getElementById('use-reference-price')?.addEventListener('click', () => {
        const value = document.getElementById('pricing-reference-price').value;
        if (numeric(value)) { price.value = Number(value).toFixed(2); recalculate(); }
    });
    const status = document.getElementById('pricing-template-status');
    const templateSelect = document.getElementById('service-template-select');
    const applyTemplate = document.getElementById('apply-service-template');
    if (applyTemplate) {
        applyTemplate.disabled = !templateSelect.value;
        templateSelect.addEventListener('change', () => { applyTemplate.disabled = !templateSelect.value; });
        applyTemplate.addEventListener('click', async () => {
            if (!templateSelect.value) return;
            if ((materials.children.length || Number(document.getElementById('pricing-labour').value)) && !window.confirm('Reemplazar el calculo por esta plantilla? El precio a cobrar no se modifica.')) return;
            applyTemplate.disabled = true;
            templateSelect.disabled = true;
            try {
                const response = await fetch(initial.template_url.replace(/\/0$/, '/' + templateSelect.value));
                if (!response.ok) throw new Error('No se pudo cargar la plantilla.');
                const result = await response.json();
                applyPricing(result.pricing);
                status.textContent = result.warnings.join(' ');
                const description = form.querySelector('[name="description"]');
                if (description && !description.value.trim()) description.value = result.name;
            } catch (error) { status.textContent = error.message; }
            finally { templateSelect.disabled = false; applyTemplate.disabled = !templateSelect.value; }
        });
    }
    const dialog = document.getElementById('pricing-refresh-dialog');
    const refresh = document.getElementById('refresh-pricing');
    refresh.addEventListener('click', async () => {
        recalculate();
        if (!pricingValid) { document.getElementById('pricing-error').focus(); return; }
        refresh.disabled = true;
        const requested = JSON.stringify(pricingData());
        try {
            const response = await fetch(initial.refresh_url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: requested });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'No se pudieron consultar los precios.');
            if (JSON.stringify(pricingData()) !== requested) throw new Error('El presupuesto cambio durante la consulta. Vuelve a actualizar.');
            pendingRefresh = result.pricing;
            const container = document.getElementById('pricing-refresh-changes');
            container.replaceChildren();
            const header = document.createElement('div'); header.className = 'pricing-change';
            for (const label of ['Concepto', 'Anterior', 'Actual']) { const span = document.createElement('strong'); span.textContent = label; header.append(span); }
            container.append(header);
            for (const change of result.changes) {
                const row = document.createElement('div'); row.className = 'pricing-change';
                const formatChange = value => value == null ? '\u2014' : (change.percent ? `${value} %` : currency(Number(value)));
                for (const value of [change.label, formatChange(change.before), formatChange(change.after)]) { const span = document.createElement('span'); span.textContent = value; row.append(span); }
                container.append(row);
            }
            const beforePrice = result.before == null ? '\u2014' : currency(Number(result.before));
            const afterPrice = result.after == null ? '\u2014' : currency(Number(result.after));
            document.getElementById('pricing-refresh-totals').textContent = result.changes.length ? `Precio sugerido: ${beforePrice} \u2192 ${afterPrice}` : 'No hay cambios de costos.';
            document.getElementById('pricing-refresh-warnings').textContent = result.warnings.join(' ');
            document.getElementById('confirm-pricing-refresh').disabled = !result.changes.length;
            dialog.showModal();
        } catch (error) { status.textContent = error.message; }
        finally { refresh.disabled = false; }
    });
    document.getElementById('confirm-pricing-refresh').addEventListener('click', () => {
        if (pendingRefresh) applyPricing(pendingRefresh);
        dialog.close();
        status.textContent = 'Costos actualizados. El precio a cobrar se conserva.';
    });
    document.getElementById('cancel-pricing-refresh').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { pendingRefresh = null; });
    recalculate();
});
