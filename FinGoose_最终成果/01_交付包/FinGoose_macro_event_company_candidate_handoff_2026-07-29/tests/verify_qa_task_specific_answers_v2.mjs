import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';


const html = path.resolve(
  'work/company_impact_high_quality_v2_candidate/ui/index.html',
);
const screenshots = path.resolve('work/qa_reasoning_pilot_v2_candidate');
const expectedIndustryCounts = [8, 8, 8, 8, 7, 7, 7, 7, 8, 9];
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
    const errors = [];
    page.on('console', message => {
      if (message.type() === 'error') errors.push(message.text());
    });
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(html).href);
    await page.waitForFunction(() => Boolean(window.FINGOOSE_COMPANY_IMPACT_V2));

    for (let index = 0; index < 10; index += 1) {
      const eventId = `event-${String(index + 1).padStart(2, '0')}`;
      await page
        .locator(`.event-button[data-event="${eventId}"]`)
        .evaluate(element => element.click());

      const stageCards = page.locator('.qa-stage-reason');
      if ((await stageCards.count()) !== 3) {
        throw new Error(`${eventId}: three horizon reasoning cards missing`);
      }
      const stageTexts = await stageCards.allInnerTexts();
      for (const marker of [
        ['首轮预期与交易反应', 'T0 + D1'],
        ['经营兑现与反馈', 'D3 + D5'],
        ['持续性与结构变化', 'D20'],
      ]) {
        if (!stageTexts.some(text => marker.every(value => text.includes(value)))) {
          throw new Error(`${eventId}: horizon reasoning missing ${marker.join('/')}`);
        }
      }
      if (new Set(stageTexts).size !== 3) {
        throw new Error(`${eventId}: horizon reasoning is duplicated`);
      }

      await page
        .locator('[data-qa-task="EVIDENCE_AUDIT"]')
        .evaluate(element => element.click());
      const auditText = await page.locator('#qa').innerText();
      for (const label of ['结论分类', '官方事实', '研究推断', '计算事实', '拒答边界']) {
        if (!auditText.includes(label)) throw new Error(`${eventId}: audit missing ${label}`);
      }
      if (!(await page.locator('.qa-evidence').count())) {
        throw new Error(`${eventId}: audit has no official evidence`);
      }

      await page
        .locator('[data-qa-task="MARKET_VALIDATION"]')
        .evaluate(element => element.click());
      if ((await page.locator('.qa-market-result').count()) !== expectedIndustryCounts[index]) {
        throw new Error(`${eventId}: market industry result count mismatch`);
      }
      await page.locator('.qa-market-result').first().evaluate(element => {
        element.open = true;
      });
      if ((await page.locator('.qa-market-result').first().locator('tbody tr').count()) !== 6) {
        throw new Error(`${eventId}: market result does not show six windows`);
      }
      const marketText = await page.locator('#qa').innerText();
      for (const label of ['行业收益', '沪深300收益', '相对收益', '阶段判定']) {
        if (!marketText.includes(label)) throw new Error(`${eventId}: market missing ${label}`);
      }
      if (eventId === 'event-07' && !marketText.includes('晚于截止日')) {
        throw new Error('event-07: post-cutoff refusal missing');
      }

      await page
        .locator('[data-qa-task="INDUSTRY_COMPANY"]')
        .evaluate(element => element.click());
      if ((await page.locator('.qa-company-answer').count()) !== 3) {
        throw new Error(`${eventId}: company answer count is not three`);
      }
      const companyText = await page.locator('#qa').innerText();
      for (const label of [
        '事件前业务披露',
        '公司传导机制',
        '限制与失效条件',
        '反证与独立混杂',
        '停复牌核验',
      ]) {
        if (!companyText.includes(label)) throw new Error(`${eventId}: company missing ${label}`);
      }

      for (const sectionId of ['timeline', 'transmission', 'industries', 'companies']) {
        if ((await page.locator(`#${sectionId}`).count()) !== 1) {
          throw new Error(`${eventId}: original section ${sectionId} missing`);
        }
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      );
      if (overflow) throw new Error(`${eventId}: horizontal overflow at ${viewport.width}px`);
    }

    if (errors.length) throw new Error(errors.join('\n'));
    await page
      .locator('.event-button[data-event="event-01"]')
      .evaluate(element => element.click());
    await page
      .locator('[data-qa-task="MARKET_VALIDATION"]')
      .evaluate(element => element.click());
    await page.screenshot({
      path: path.join(screenshots, `ui-task-specific-${viewport.width}.png`),
      fullPage: true,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
