const { chromium } = require(process.argv[2]);
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'chrome' });
    try {
        const page = await browser.newPage();
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(pathToFileURL(process.argv[3] || path.join(os.tmpdir(), 'peluqueria-google-import.html')).href);
            await page.getByRole('heading', { name: 'Importar desde Google' }).waitFor();
            assert.equal(await page.locator('.google-import-row').count(), 3);
            await page.locator('[value="day"][type="checkbox"]').check();
            await page.locator('[name="client_day"]').selectOption('1');
            await page.locator('[name="time_day"]').fill('13:30');
            assert(await page.locator('[value="linked"][type="checkbox"]').isDisabled());
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
            const filename = path.join(os.tmpdir(), `peluqueria-import-${width}.png`);
            await page.screenshot({ path: filename, fullPage: true });
            console.log(filename);
        }
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
