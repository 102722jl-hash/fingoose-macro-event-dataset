import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const expectedCounts = {
  'event-01': 8,
  'event-02': 8,
  'event-03': 8,
  'event-04': 8,
  'event-05': 7,
  'event-06': 7,
  'event-07': 7,
  'event-08': 7,
  'event-09': 8,
  'event-10': 9,
};
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

    const dataErrors = await page.evaluate(expected => {
      const errors = [];
      for (const event of window.FINGOOSE_COMPANY_IMPACT_V2.events || []) {
        const impacts = event.industry_impacts || [];
        if (impacts.length !== expected[event.event_id]) {
          errors.push(`${event.event_id}: industry count ${impacts.length}`);
        }
        for (const impact of impacts) {
          const chain = impact.mechanism_chain || {};
          if ((chain.nodes || []).length !== 7) {
            errors.push(`${impact.event_industry_mapping_id}: mechanism nodes not 7`);
          }
          const market = impact.market_window || {};
          if (market.window_status !== 'AVAILABLE') {
            errors.push(`${impact.event_industry_mapping_id}: market not available`);
          }
          const continuous = market.continuous_window || [];
          const observations = Array.isArray(continuous)
            ? continuous
            : continuous.observations || [];
          if (observations.length !== 41) {
            errors.push(`${impact.event_industry_mapping_id}: continuous points ${observations.length}`);
          }
          if (event.event_id !== 'event-01') {
            for (const confounder of chain.confounders || []) {
              if ((confounder.analysis_zh || '').length < 120) {
                errors.push(`${confounder.confounder_id}: analysis too short`);
              }
              if (!(confounder.distinguishing_tests_zh || []).length) {
                errors.push(`${confounder.confounder_id}: tests missing`);
              }
            }
          }
        }
      }
      return errors;
    }, expectedCounts);
    if (dataErrors.length) throw new Error(dataErrors.join('\n'));

    for (const [eventId, expectedCount] of Object.entries(expectedCounts)) {
      await page
        .locator(`.event-button[data-event="${eventId}"]`)
        .evaluate(element => element.click());
      await page
        .getByText('行业板块链', { exact: true })
        .evaluate(element => element.click());
      const branches = page.locator('[data-industry-mapping]');
      if ((await branches.count()) !== expectedCount) {
        throw new Error(`${eventId}: rendered industry count mismatch`);
      }
      await branches.first().click();
      await page.locator('.industry-detail').waitFor();
      if ((await page.locator('.industry-detail .mechanism-step').count()) !== 7) {
        throw new Error(`${eventId}: rendered mechanism steps not 7`);
      }
      if ((await page.locator('.industry-detail .industry-chart svg').count()) !== 2) {
        throw new Error(`${eventId}: normalized/raw charts missing`);
      }
      if ((await page.locator('.industry-detail .industry-chart polyline').count()) < 4) {
        throw new Error(`${eventId}: industry or CSI300 chart line missing`);
      }
      if ((await page.locator('.industry-detail .industry-concurrence').count()) < 1) {
        throw new Error(`${eventId}: confounder records missing`);
      }
      const detailText = await page.locator('.industry-detail').innerText();
      for (const label of ['证据来源', '竞争解释', '归因边界', '反证']) {
        if (!detailText.includes(label)) {
          throw new Error(`${eventId}: detail label missing: ${label}`);
        }
      }
      if (eventId !== 'event-01') {
        for (const label of ['混杂分析', '区分检验']) {
          if (!detailText.includes(label)) {
            throw new Error(`${eventId}: confounder label missing: ${label}`);
          }
        }
      }
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth + 1,
      );
      if (overflow) {
        throw new Error(`${eventId}: page horizontal overflow at ${viewport.width}`);
      }
    }
    if (browserErrors.length) throw new Error(browserErrors.join('\n'));
    await page.close();
  }
} finally {
  await browser.close();
}
