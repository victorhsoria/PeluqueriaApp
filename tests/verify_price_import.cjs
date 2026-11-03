const { chromium } = require(process.argv[2]);
const assert = require('node:assert/strict');
const os = require('node:os');
const path = require('node:path');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'chrome' });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const base = 'http://127.0.0.1:5073';
        const workbook = await (await page.request.get(base + '/__test/list.xlsx')).body();
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 950 });
            await page.goto(base + '/products/prices/import');
            await page.locator('[name="file"]').setInputFiles({ name: 'lista-proveedor.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: workbook });
            await Promise.all([page.waitForURL('**/products/prices/import'), page.getByRole('button', { name: 'Generar vista previa' }).click()]);
            await page.locator('#price-review-form').waitFor();
            assert.equal(await page.locator('[name="row_0"]').inputValue(), '1');
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => scrollTo(0, 0));
            const file = path.join(os.tmpdir(), `peluqueria-excel-${width}.png`);
            await page.screenshot({ path: file, fullPage: true });
            console.log(file);
            await page.locator('[name="status"]').first().selectOption('all');
            await Promise.all([page.waitForURL('**status=all*'), page.getByRole('button', { name: 'Filtrar', exact: true }).click()]);
            assert.equal(await page.locator('.price-import-table tbody tr').count(), 50);
            await Promise.all([page.waitForURL('**page=2*'), page.getByRole('button', { name: /Siguiente/ }).click()]);
            assert.equal(await page.locator('.price-import-table tbody tr').count(), 10);
            await Promise.all([page.waitForURL('**page=1*'), page.getByRole('button', { name: /Anterior/ }).click()]);
            page.once('dialog', dialog => dialog.accept());
            await Promise.all([page.waitForURL('**/products'), page.getByRole('button', { name: 'Confirmar y actualizar precios' }).click()]);
            const product = (await (await page.request.get(base + '/api/products_list')).json())[0];
            assert.equal(product.wholesale_price, 200);
            assert.equal(product.stock, 5);
            const html = await page.content();
            assert(html.includes('260,00'));
        }
        const manualWorkbook = await (await page.request.get(base + '/__test/list.xlsx?unmatched=1')).body();
        await page.goto(base + '/products/prices/import');
        await page.locator('[name="file"]').setInputFiles({ name: 'manual.xlsx', buffer: manualWorkbook });
        await page.getByRole('button', { name: 'Generar vista previa' }).click();
        await page.locator('[name="row_0"]').selectOption('1');
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', { name: 'Confirmar y actualizar precios' }).click();
        await page.locator('.flash-warning').waitFor();
        assert.equal((await (await page.request.get(base + '/api/products_list')).json())[0].wholesale_price, 200);
        page.once('dialog', dialog => dialog.accept());
        await Promise.all([page.waitForURL('**/products'), page.getByRole('button', { name: 'Confirmar y actualizar precios' }).click()]);
        assert.equal((await (await page.request.get(base + '/api/products_list')).json())[0].wholesale_price, 300);
        const renamed = await (await page.request.get(base + '/__test/list.xlsx?unmatched=1&rename=1')).body();
        await page.goto(base + '/products/prices/import');
        await page.locator('[name="file"]').setInputFiles({ name: 'siguiente-lista.xlsx', buffer: renamed });
        await page.getByRole('button', { name: 'Generar vista previa' }).click();
        await page.locator('[name="row_0"]').waitFor();
        assert.equal(await page.locator('[name="row_0"]').inputValue(), '1');
        assert((await page.locator('.price-import-table').textContent()).includes('Vinculo guardado'));
        assert.deepEqual(errors, []);
        console.log('Desktop/mobile Excel preview, pagination, confirmation and stock: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
