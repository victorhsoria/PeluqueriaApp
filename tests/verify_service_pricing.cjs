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
            await page.goto('http://127.0.0.1:5065/clients/1/services/add');
            await page.locator('[name="date"]').fill('2026-10-19');
            await page.locator('[name="description"]').fill('Color de raiz');
            await page.locator('#pricing-enabled').check();
            for (const values of [
                { label: 'Tintura', package_cost: '12000', package_quantity: '60', quantity: '30', unit: 'g' },
                { label: 'Oxidante', package_cost: '10000', package_quantity: '1000', quantity: '100', unit: 'ml' },
                { label: 'Descartables', package_cost: '500', package_quantity: '1', quantity: '1', unit: 'unidad' }
            ]) {
                await page.locator('#add-material').click();
                const row = page.locator('.service-material').last();
                if (values.label === 'Tintura') {
                    await row.locator('[data-product]').selectOption('1');
                    assert.equal(await row.locator('[data-key="package_cost"]').inputValue(), '12000');
                }
                for (const [key, value] of Object.entries(values)) {
                    const input = row.locator(`[data-key="${key}"]`);
                    if (key === 'unit') await input.selectOption(value);
                    else await input.fill(value);
                }
            }
            await page.locator('#pricing-labour').fill('10000');
            await page.locator('#pricing-overhead').fill('2500');
            await page.locator('#pricing-margin').fill('30');
            await page.locator('.service-material').first().locator('[data-key="client_supplied"]').check();
            assert((await page.locator('#summary-materials').textContent()).includes('1.500'));
            await page.locator('.service-material').first().locator('[data-key="client_supplied"]').uncheck();
            await page.locator('#add-product-btn').click();
            await page.locator('#used-products-container select').selectOption('1');
            await page.locator('#use-suggested-price').click();
            assert.equal(await page.locator('#price').inputValue(), '28571.43');
            assert((await page.locator('#summary-total').textContent()).includes('20.000'));
            await page.locator('#pricing-margin').fill('100');
            assert(await page.locator('#use-suggested-price').isDisabled());
            await page.locator('#pricing-margin').fill('30');
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => { document.activeElement.blur(); scrollTo(0, 0); });
            const file = path.join(os.tmpdir(), `peluqueria-pricing-${width}.png`);
            await page.screenshot({ path: file, fullPage: true });
            console.log(file);
            await page.locator('#price').fill('29000');
            await Promise.all([page.waitForURL('**/clients/1'), page.getByRole('button', { name: 'Guardar trabajo' }).click()]);
            assert.equal((await page.request.get('http://127.0.0.1:5065/clients/1')).status(), 200);
            const editPath = await page.locator('a[href*="/services/edit/"]').last().getAttribute('href');
            await page.goto(`http://127.0.0.1:5065${editPath}`);
            assert.equal(await page.locator('#price').inputValue(), '29000.00');
            assert.equal(await page.locator('.service-material').count(), 3);
            const saved = JSON.parse(await page.locator('#service-initial-data').textContent());
            assert.equal(saved.pricing.suggested_price, '28571.43');
            assert.equal(saved.pricing.materials[0].product_id, 1);
            assert.equal(await page.locator('#used-products-container select').inputValue(), '1');
        }
        assert.deepEqual(errors, []);
        console.log('Desktop/mobile calculation, validation, save and edit: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
