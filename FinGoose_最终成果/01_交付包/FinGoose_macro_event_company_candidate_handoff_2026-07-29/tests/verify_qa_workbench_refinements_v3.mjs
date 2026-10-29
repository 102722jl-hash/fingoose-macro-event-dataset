import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';


const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const screenshots = path.resolve('work/qa_reasoning_pilot_v2_candidate');
const counts = [8, 8, 8, 8, 7, 7, 7, 7, 8, 9];
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
      await page.locator('[data-qa-task="MAIN_REASONING"]').evaluate(element => element.click());
      await page.locator('[data-horizon-view="IMMEDIATE"]').click();
      if ((await page.locator('.qa-stage-reason:not(.qa-stage-hidden)').count()) !== 1) throw new Error(`${eventId}: immediate toggle failed`);
      if ((await page.locator('[data-impact-horizon]:not(.qa-stage-hidden)').count()) !== counts[index]) throw new Error(`${eventId}: impact horizon toggle failed`);
      await page.locator('[data-horizon-view="ALL"]').click();

      await page.locator('[data-qa-task="EVIDENCE_AUDIT"]').evaluate(element => element.click());
      const evidenceCount = await page.locator('.qa-evidence').count();
      if (!evidenceCount || !(await page.locator('#qa-evidence-tier').count()) || !(await page.locator('#qa-evidence-query').count())) throw new Error(`${eventId}: evidence controls missing`);
      await page.locator('#qa-evidence-query').fill('WHO');
      if ((await page.locator('.qa-evidence:not([hidden])').count()) > evidenceCount) throw new Error(`${eventId}: evidence query filter failed`);
      await page.locator('#qa-evidence-query').fill('');
      await page.locator('.qa-source-original').first().locator('summary').click();
      if (!(await page.locator('.qa-source-original').first().locator('blockquote').isVisible())) throw new Error(`${eventId}: evidence expansion failed`);
      if (!(await page.locator('#qa-refusal-scope').count())) throw new Error(`${eventId}: refusal filter missing`);

      await page.locator('[data-qa-task="MARKET_VALIDATION"]').evaluate(element => element.click());
      if ((await page.locator('.qa-market-result').count()) !== counts[index]) throw new Error(`${eventId}: market count mismatch`);
      if (!(await page.locator('.qa-strength').count())) throw new Error(`${eventId}: market strength missing`);
      const marketText = await page.locator('#qa').innerText();
      if (!marketText.includes('统计偏弱')) throw new Error(`${eventId}: weak-strength label missing`);
      if (eventId === 'event-07' && !marketText.includes('晚于截止日')) throw new Error('event-07: cutoff notice missing');

      await page.locator('[data-qa-task="INDUSTRY_COMPANY"]').evaluate(element => element.click());
      if ((await page.locator('.qa-company-answer').count()) !== 3) throw new Error(`${eventId}: company count mismatch`);
      if (!(await page.locator('.qa-selection-reasons').count())) throw new Error(`${eventId}: selection reason block missing`);
      if (!(await page.locator('#qa').innerText()).includes('入选理由')) throw new Error(`${eventId}: selection reason label missing`);

      for (const sectionId of ['timeline', 'transmission', 'industries', 'companies']) {
        if ((await page.locator(`#${sectionId}`).count()) !== 1) throw new Error(`${eventId}: original section ${sectionId} missing`);
      }
      if (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)) throw new Error(`${eventId}: horizontal overflow`);
    }
    if (errors.length) throw new Error(errors.join('\n'));
    await page.locator('.event-button[data-event="event-01"]').evaluate(element => element.click());
    await page.locator('[data-qa-task="MAIN_REASONING"]').evaluate(element => element.click());
    await page.screenshot({ path: path.join(screenshots, `ui-refinements-${viewport.width}.png`), fullPage: true });
    await page.close();
  }
} finally {
  await browser.close();
}
