import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';


const html = path.resolve(
  'work/company_impact_high_quality_v2_candidate/ui/index.html',
);
const screenshots = path.resolve('work/qa_reasoning_pilot_v2_candidate');
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
    await page.waitForSelector('.qa-impact-stage');

    for (let index = 1; index <= 10; index += 1) {
      const eventId = `event-${String(index).padStart(2, '0')}`;
      await page
        .locator(`.event-button[data-event="${eventId}"]`)
        .evaluate(element => element.click());
      const audit = await page.evaluate(() => {
        const visible = document.querySelector('#qa')?.innerText || '';
        const firstSource = document.querySelector('.qa-evidence');
        const impactCount = document.querySelectorAll('.qa-impact').length;
        return {
          impactCount,
          stageCount: document.querySelectorAll('.qa-impact-stage').length,
          sourceCount: document.querySelectorAll('.qa-evidence').length,
          collapsedOriginal: Boolean(
            firstSource?.querySelector('details:not([open]) blockquote'),
          ),
          hasChineseFields: [
            '中文事实摘录',
            '可观察驱动',
            '经营变量',
            '财务变量',
            '成立条件',
            '失效条件',
          ].every(label => visible.includes(label)),
          visibleRawEnums: [
            'CORE_DIRECT',
            'SECOND_ORDER',
            'CONDITIONAL',
            'MIXED',
            'POSITIVE',
            'NEGATIVE',
          ].filter(token => visible.includes(token)),
          overflow:
            document.documentElement.scrollWidth >
            document.documentElement.clientWidth + 1,
        };
      });
      if (audit.stageCount !== audit.impactCount * 3) {
        throw new Error(`${eventId} industry detail incomplete: ${JSON.stringify(audit)}`);
      }
      if (!audit.sourceCount || !audit.collapsedOriginal || !audit.hasChineseFields) {
        throw new Error(`${eventId} Chinese detail incomplete: ${JSON.stringify(audit)}`);
      }
      if (audit.visibleRawEnums.length || audit.overflow || errors.length) {
        throw new Error(
          `${eventId} localization regression: ${JSON.stringify({ audit, errors })}`,
        );
      }
    }
    await page
      .locator('.event-button[data-event="event-01"]')
      .evaluate(element => element.click());
    await page.screenshot({
      path: path.join(screenshots, `ui-chinese-detail-all-${viewport.width}.png`),
      fullPage: true,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
