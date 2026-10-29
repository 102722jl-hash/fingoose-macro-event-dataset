import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const screenshots = path.resolve('work/qa_reasoning_pilot_v2_candidate');
const industryCounts = [8, 8, 8, 8, 7, 7, 7, 7, 8, 9];
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});

try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(html).href);
    await page.waitForFunction(() => Boolean(window.FINGOOSE_COMPANY_IMPACT_V2));

    for (let index = 0; index < 10; index += 1) {
      const eventId = `event-${String(index + 1).padStart(2, '0')}`;
      await page.locator(`.event-button[data-event="${eventId}"]`).evaluate(element => element.click());
      if ((await page.locator('[data-closure-node-step]').count()) !== 7) throw new Error(`${eventId}: seven-step closure missing`);
      if ((await page.locator('.event-study-table tbody tr').count()) !== 4) throw new Error(`${eventId}: event-study windows missing`);
      for (const key of ['PRETREND', 'EVENT', 'SHORT', 'MEDIUM']) {
        if ((await page.locator(`[data-study-window="${key}"]`).count()) !== 1) throw new Error(`${eventId}: ${key} window missing`);
      }
      if ((await page.locator('.matrix-table tbody tr').count()) !== industryCounts[index]) throw new Error(`${eventId}: matrix row count mismatch`);

      const evidenceButton = page.locator('.closure-evidence-button:not(.missing)').first();
      if (!(await evidenceButton.count())) throw new Error(`${eventId}: linked evidence missing`);
      await evidenceButton.click();
      if ((await page.locator('.closure-evidence-entry.highlight').count()) !== 1) throw new Error(`${eventId}: evidence highlight failed`);
      const reverseButton = page.locator('.closure-evidence-entry.highlight [data-closure-node-step-target]').first();
      if (!(await reverseButton.count())) throw new Error(`${eventId}: reverse evidence linkage missing`);
      await reverseButton.click();

      await page.locator('[data-matrix-industry]').nth(Math.min(1, industryCounts[index] - 1)).click();
      if ((await page.locator('.matrix-table tr.active').count()) !== 1) throw new Error(`${eventId}: industry matrix linkage failed`);
      const matrixCompany = page.locator('[data-matrix-company]').first();
      if (await matrixCompany.count()) {
        await matrixCompany.click();
        if (!(await page.locator('#companies > .detail').count())) throw new Error(`${eventId}: company matrix linkage failed`);
      }

      for (const selector of ['#qa', '#timeline', '#transmission', '#industries', '#companies', '.chart-wrap svg', '.industry-concurrence-list']) {
        if (!(await page.locator(selector).count())) throw new Error(`${eventId}: original content ${selector} missing`);
      }
      if (eventId === 'event-07' && !(await page.locator('.cutoff-gate').count())) throw new Error('event-07: cutoff attribution gate missing');
      if (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)) throw new Error(`${eventId}: page horizontal overflow`);
    }

    if (errors.length) throw new Error(errors.join('\n'));
    await page.locator('.event-button[data-event="event-01"]').evaluate(element => element.click());
    await page.locator('#industries').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(screenshots, `industry-research-workspace-v3-${viewport.width}.png`), fullPage: false });
    await page.close();
  }
} finally {
  await browser.close();
}
