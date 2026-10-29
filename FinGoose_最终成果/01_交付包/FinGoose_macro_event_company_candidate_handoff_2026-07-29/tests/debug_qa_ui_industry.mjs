import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(
    pathToFileURL(
      path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html'),
    ).href,
  );
  await page.getByText('行业板块链', { exact: true }).click();
  const before = await page.evaluate(() => ({
    transmissionMode: state.transmissionMode,
    industryMappingId: state.industryMappingId,
    branchCount: document.querySelectorAll('[data-industry-mapping]').length,
    detailCount: document.querySelectorAll('.industry-detail').length,
  }));
  await page
    .locator('[data-industry-mapping="event-industry-event-01-801170"]')
    .click();
  await page.waitForTimeout(100);
  const after = await page.evaluate(() => ({
    transmissionMode: state.transmissionMode,
    industryMappingId: state.industryMappingId,
    branchCount: document.querySelectorAll('[data-industry-mapping]').length,
    detailCount: document.querySelectorAll('.industry-detail').length,
    industryText: document.querySelector('#industries')?.innerText.slice(0, 400),
  }));
  console.log(JSON.stringify({ before, after, errors }, null, 2));
} finally {
  await browser.close();
}
