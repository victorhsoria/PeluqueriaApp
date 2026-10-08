const { chromium } = require(process.argv[2] || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.argv[3] || undefined });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5055';
        const response = await page.request.get(`${base}/api/clients_list`);
        const clients = await response.json();
        for (const width of [1440, 390]) {
            await page.setViewportSize({ width, height: 900 });
            for (const route of ['/', '/appointments/calendar', ...(clients.length ? [`/clients/${clients[0].id}`] : [])]) {
                await page.goto(base + route);
                if (route.includes('calendar')) {
                    await page.locator('.fc-timegrid').waitFor();
                    for (const label of ['Mes', 'Semana', 'Día']) {
                        await page.getByRole('button', { name: label, exact: true }).click();
                        assert(await page.locator('.fc-view').isVisible());
                    }
                } else if (route.includes('clients')) {
                    for (const name of ['evaluacion', 'formulas', 'fotos', 'historial', 'datos']) {
                        await page.locator(`[data-client-tab="${name}"]`).click();
                        await page.locator(`#${name}`).waitFor({ state: 'visible' });
                        assert(await page.locator(`#${name}`).isVisible());
                        assert.equal(await page.locator('[data-client-panel]:visible').count(), name === 'historial' ? 2 : 1);
                    }
                } else {
                    assert(await page.locator('.dashboard-hero-image').evaluate(image => image.complete && image.naturalWidth > 0));
                }
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${route} overflows at ${width}`);
                const primary = page.locator('.dashboard-button').first();
                assert.notEqual(await primary.evaluate(button => getComputedStyle(button).backgroundColor), 'rgba(0, 0, 0, 0)');
                const filename = path.join(os.tmpdir(), `peluqueria-${width}-${route.includes('calendar') ? 'calendar' : route.includes('clients') ? 'client' : 'home'}.png`);
                await page.screenshot({ path: filename, fullPage: true });
                console.log(filename);
            }
        }
        assert.deepEqual(errors, []);
        console.log('Desktop/mobile, calendar views, client tabs and images: OK');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
