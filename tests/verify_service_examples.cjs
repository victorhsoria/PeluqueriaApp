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
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 950 });
            await page.goto('http://127.0.0.1:5065/service-templates');
            await Promise.all([page.waitForURL('**/service-templates'), page.getByRole('button', { name: 'Cargar ejemplos Bucles' }).click()]);
            await page.locator('.service-template-row').first().waitFor();
            assert.equal(await page.locator('.service-template-row').count(), 6);
            const row = page.locator('.service-template-row').filter({ hasText: 'Color - corto (ejemplo Bucles)' });
            const edit = await row.getByRole('link', { name: 'Editar', exact: true }).getAttribute('href');
            const id = edit.split('/')[2];
            await page.goto('http://127.0.0.1:5065' + edit);
            assert.equal(await page.locator('#pricing-reference-price').inputValue(), width === 1440 ? '39999.00' : '35000.00');
            assert.equal(await page.locator('#pricing-costs-confirmed').isChecked(), false);
            assert.equal(await page.locator('#summary-total').textContent(), 'Sin verificar');
            assert(await page.locator('#pricing-reference-origin').isVisible());
            await page.locator('#pricing-reference-price').fill('35000');
            await Promise.all([page.waitForURL('**/service-templates'), page.getByRole('button', { name: 'Guardar plantilla' }).click()]);
            await page.goto('http://127.0.0.1:5065/clients/1/services/add');
            await page.locator('#service-template-select').selectOption(id);
            await page.locator('#apply-service-template').click();
            await page.waitForFunction(() => document.getElementById('pricing-reference-price').value === '35000.00');
            assert(await page.locator('#use-suggested-price').isDisabled());
            await page.locator('#use-reference-price').click();
            assert.equal(await page.locator('#price').inputValue(), '35000.00');
            assert.equal(await page.locator('#summary-profit').textContent(), '\u2014');
            assert.equal(await page.locator('#summary-margin').textContent(), '\u2014');
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => { document.activeElement.blur(); scrollTo(0, 0); });
            const filename = path.join(os.tmpdir(), `peluqueria-bucles-${width}.png`);
            await page.screenshot({ path: filename, fullPage: true });
            console.log(filename);
            await page.locator('#pricing-labour').fill('10000');
            await page.locator('#pricing-overhead').fill('2500');
            await page.locator('#pricing-costs-confirmed').check();
            await page.locator('#use-suggested-price').click();
            assert.equal(await page.locator('#price').inputValue(), '12500.00');
            await page.locator('#use-reference-price').click();
            await page.locator('[name="date"]').fill('2026-11-02');
            await Promise.all([page.waitForURL('**/clients/1'), page.getByRole('button', { name: 'Guardar trabajo' }).click()]);
            const work = await page.locator('a[href*="/services/edit/"]').last().getAttribute('href');
            await page.goto('http://127.0.0.1:5065' + work);
            const saved = JSON.parse(await page.locator('#service-initial-data').textContent());
            assert.equal(saved.pricing.reference_price, '35000.00');
            assert.equal(saved.pricing.total_cost, '12500.00');
            assert.equal(await page.locator('#price').inputValue(), '35000.00');
        }
        assert.deepEqual(errors, []);
        console.log('Editable reference prices, unknown costs, explicit pricing and persistence: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
