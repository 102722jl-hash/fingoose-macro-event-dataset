import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
});

try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('console', message => {
      if (message.type() === 'error') errors.push(message.text());
    });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(pathToFileURL(html).href);
    const activeEvent = await page.locator('.event-button.active').getAttribute('data-event');
    if (activeEvent !== 'event-01') {
      throw new Error('default active event is ' + activeEvent + ', expected event-01');
    }
    await page.getByText('行业板块链', { exact: true }).click();

    const branches = page.locator('[data-industry-mapping]');
    if (await branches.count() !== 8) {
      throw new Error(`event-01 industry branch count is ${await branches.count()}, expected 8`);
    }

    await page.locator('[data-industry-mapping="event-industry-event-01-801170"]').click();
    await page.locator('.industry-detail').waitFor();

    const mechanismSteps = await page.locator('.industry-detail .mechanism-step').count();
    if (mechanismSteps !== 7) {
      throw new Error(`traffic industry mechanism step count is ${mechanismSteps}, expected 7`);
    }
    if (await page.locator('.industry-detail .industry-chart svg').count() !== 2) {
      throw new Error('normalized/raw industry chart views are missing');
    }
    if (await page.locator('.industry-detail a.evidence-link').count() < 1) {
      throw new Error('verified source links are missing from the industry detail');
    }

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    if (overflow) {
      const offenders = await page.evaluate(() => {
        const width = document.documentElement.clientWidth;
        return [...document.querySelectorAll('*')]
          .map(element => {
            const rect = element.getBoundingClientRect();
            let ancestor = element.parentElement;
            let clippedByAncestor = false;
            while (ancestor && ancestor !== document.body) {
              if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(ancestor).overflowX)) {
                clippedByAncestor = true;
                break;
              }
              ancestor = ancestor.parentElement;
            }
            return {
              tag: element.tagName,
              className: String(element.className || '').slice(0, 120),
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              width: Math.round(rect.width),
              scrollWidth: element.scrollWidth,
              clippedByAncestor,
            };
          })
          .filter(row => row.right > width + 1 && !row.clippedByAncestor)
          .slice(0, 20);
      });
      const context = await page.evaluate(() => {
        const wrap = document.querySelector('.industry-detail .table-wrap');
        const detail = document.querySelector('.industry-detail');
        const metrics = element => {
          if (!element) return null;
          const rect = element.getBoundingClientRect();
          const style = getComputedStyle(element);
          return {
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
            overflowX: style.overflowX,
            minWidth: style.minWidth,
          };
        };
        return {
          documentClientWidth: document.documentElement.clientWidth,
          documentScrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth,
          detail: metrics(detail),
          tableWrap: metrics(wrap),
          overflowingContainers: [...document.querySelectorAll('.industry-detail, .industry-detail *')]
            .map(element => ({
              tag: element.tagName,
              className: String(element.className || '').slice(0, 120),
              clientWidth: element.clientWidth,
              scrollWidth: element.scrollWidth,
              overflowX: getComputedStyle(element).overflowX,
              text: String(element.textContent || '').replace(/s+/g, ' ').trim().slice(0, 220),
            }))
            .filter(row => row.scrollWidth > row.clientWidth + 1 && row.overflowX === 'visible')
            .slice(0, 30),
        };
      });
      throw new Error('page-level horizontal overflow at ' + viewport.width + 'px: ' + JSON.stringify({ context, offenders }));
    }
    if (errors.length) throw new Error(errors.join('\n'));

    await page.screenshot({
      path: `work/event_01_industry_closure_v2_candidate/ui-${viewport.width}.png`,
      fullPage: true,
    });
    await page.close();
  }
} finally {
  await browser.close();
}
