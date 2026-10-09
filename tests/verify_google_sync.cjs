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
        await page.clock.install();
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto('http://127.0.0.1:5056/appointments/calendar');
            await page.locator('.fc-event').first().waitFor();
            assert.equal(await page.locator('.fc-event').count(), 3);
            assert(await page.locator('.fc-daygrid-event').isVisible());
            assert(await page.getByText('Recordatorio de Google', { exact: true }).first().isVisible());
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
            await page.evaluate(() => window.scrollTo(0, 0));
            const filename = path.join(os.tmpdir(), `peluqueria-sync-${width}.png`);
            await page.screenshot({ path: filename, fullPage: true });
            console.log(filename);
        }
        await page.request.post('http://127.0.0.1:5056/__test/change');
        const response = page.waitForResponse(response => response.url().includes('/api/google-calendar/refresh'));
        await page.clock.fastForward(61000);
        await response;
        await page.getByText('Evento actualizado automaticamente', { exact: true }).first().waitFor();
        assert.deepEqual(errors, []);
        console.log('Google events, all-day events and automatic refresh: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
