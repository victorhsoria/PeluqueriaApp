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
        const workbook = await (await page.request.get(base + '/__test/list.xlsx?unmatched=1')).body();
        await page.goto(base + '/products/prices/import');
        await page.locator('[name="file"]').setInputFiles({ name: 'productos-nuevos.xlsx', buffer: workbook });
        await page.getByRole('button', { name: 'Generar vista previa' }).click();
        const select = page.locator('[name="row_0"]');
        await select.waitFor();
        await select.selectOption('new');
        await page.locator('[name="new_brand_0"]').fill('Marca');
        await page.locator('[name="new_description_0"]').fill('Champu nuevo seleccionado');
        await page.locator('[name="new_percentage_0"]').fill('25');
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 950 });
            assert(await page.locator('.price-new-fields').isVisible());
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => { document.activeElement.blur(); scrollTo(0, 0); });
            const file = path.join(os.tmpdir(), `peluqueria-excel-new-${width}.png`);
            await page.screenshot({ path: file, fullPage: true });
            console.log(file);
        }
        await page.getByRole('button', { name: 'Guardar selecci\u00f3n' }).click();
        await page.locator('[name="row_0"]').waitFor();
        assert.equal(await page.locator('[name="row_0"]').inputValue(), 'new');
        assert((await page.locator('.price-import-table').textContent()).includes('375,00'));
        assert.equal((await (await page.request.get(base + '/api/products_list')).json()).length, 1);
        page.once('dialog', dialog => dialog.accept());
        await Promise.all([page.waitForURL('**/products'), page.getByRole('button', { name: 'Confirmar importaci\u00f3n' }).click()]);
        const products = await (await page.request.get(base + '/api/products_list')).json();
        assert.equal(products.length, 2);
        const created = products.find(product => product.description === 'Champu nuevo seleccionado');
        assert.equal(created.stock, 0);
        assert.equal(created.wholesale_price, 300);
        assert((await page.content()).includes('375,00'));
        await page.goto(base + '/products/prices/import');
        await page.locator('[name="file"]').setInputFiles({ name: 'siguiente-lista.xlsx', buffer: workbook });
        await page.getByRole('button', { name: 'Generar vista previa' }).click();
        await page.locator('[name="row_0"]').waitFor();
        assert.equal(await page.locator('[name="row_0"]').inputValue(), String(created.id));
        assert((await page.locator('.price-import-table').textContent()).includes('Vinculo guardado'));
        page.once('dialog', dialog => dialog.accept());
        await Promise.all([page.waitForURL('**/products'), page.getByRole('button', { name: 'Confirmar importaci\u00f3n' }).click()]);
        assert.equal((await (await page.request.get(base + '/api/products_list')).json()).length, 2);
        assert.deepEqual(errors, []);
        console.log('New products: explicit selection, reviewed markup, stock zero and no duplicate on reimport: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
