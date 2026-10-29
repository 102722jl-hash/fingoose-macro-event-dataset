import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const screenshots = path.resolve('work/qa_reasoning_pilot_v2_candidate');
const eventIds = Array.from({ length: 10 }, (_, index) =>
  `event-${String(index + 1).padStart(2, '0')}`,
);
const taskTypes = [
  'MAIN_REASONING',
  'EVIDENCE_AUDIT',
  'MARKET_VALIDATION',
  'INDUSTRY_COMPANY',
];
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.CHROME_PATH ||
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
});

try {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 390, height: 844 },
  ]) {
    const page = await browser.newPage({ viewport });
    const browserErrors = [];
    page.on('console', message => {
      if (message.type() === 'error') browserErrors.push(message.text());
    });
    page.on('pageerror', error => browserErrors.push(error.message));
    await page.goto(pathToFileURL(html).href);
    await page.waitForFunction(() => Boolean(window.FINGOOSE_COMPANY_IMPACT_V2));

    const dataAudit = await page.evaluate(() => {
      const bundle = window.FINGOOSE_COMPANY_IMPACT_V2;
      const text = JSON.stringify(bundle);
      return {
        eventCount: (bundle.events || []).length,
        qaCounts: (bundle.events || []).map(event => (event.qa || []).length),
        hiddenLeak:
          text.includes('expected_evidence_ids') ||
          text.includes('hard_failure_labels') ||
          text.includes('evaluator_only'),
      };
    });
    if (dataAudit.eventCount !== 10 || dataAudit.qaCounts.some(count => count !== 4)) {
      throw new Error('public bundle does not contain four Q&A records for all ten events');
    }
    if (dataAudit.hiddenLeak) throw new Error('hidden evaluator fields leaked into UI bundle');

    for (const eventId of eventIds) {
      await page
        .locator(`.event-button[data-event="${eventId}"]`)
        .evaluate(element => element.click());
      if ((await page.locator('[data-qa-task]').count()) !== 4) {
        throw new Error(`${eventId}: rendered Q&A tab count is not 4`);
      }
      for (const taskType of taskTypes) {
        await page
          .locator(`[data-qa-task="${taskType}"]`)
          .evaluate(element => element.click());
        if ((await page.locator('.qa-layer').count()) !== 4) {
          throw new Error(`${eventId}/${taskType}: four answer layers missing`);
        }
        if ((await page.locator('.qa-step').count()) !== 7) {
          throw new Error(`${eventId}/${taskType}: seven-step mechanism missing`);
        }
        if ((await page.locator('[data-qa-jump]').count()) !== 4) {
          throw new Error(`${eventId}/${taskType}: drill-down links missing`);
        }
      }
      for (const sectionId of ['timeline', 'transmission', 'industries', 'companies']) {
        if ((await page.locator(`#${sectionId}`).count()) !== 1) {
          throw new Error(`${eventId}: original section ${sectionId} missing`);
        }
      }
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth + 1,
      );
      if (overflow) {
        throw new Error(`${eventId}: page horizontal overflow at ${viewport.width}px`);
      }
    }
    if (browserErrors.length) throw new Error(browserErrors.join('\n'));
    await page
      .locator('.event-button[data-event="event-01"]')
      .evaluate(element => element.click());
    await page.screenshot({
      path: path.join(screenshots, `ui-${viewport.width}.png`),
      fullPage: true,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
