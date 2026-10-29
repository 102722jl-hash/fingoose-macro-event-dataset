const { chromium } = require("playwright");
const fs = require("fs");
const crypto = require("crypto");

const url = process.argv[2];
const output = process.argv[3];
if (!url || !output) throw new Error("usage: node validate_versioned_ui_candidate.js <url> <output-dir>");

const newEventIds = Array.from({ length: 7 }, (_, index) => `event-${String(index + 11).padStart(2, "0")}`);
const expectedSections = ["事件概览", "研究问答", "事件时间线", "动态传导链", "行业影响", "公司影响"];

function sha256(path) {
  return crypto.createHash("sha256").update(fs.readFileSync(path)).digest("hex");
}

async function inspectEvent(page, eventId) {
  await page.locator(`[data-event="${eventId}"]`).evaluate((element) => element.click());
  await page.waitForTimeout(80);
  const qaDirectAnswers = [];
  for (const task of ["MAIN_REASONING", "EVIDENCE_AUDIT", "MARKET_VALIDATION", "INDUSTRY_COMPANY"]) {
    await page.locator(`[data-qa-task="${task}"]`).evaluate((element) => element.click());
    await page.waitForTimeout(40);
    qaDirectAnswers.push((await page.locator(".qa-focus").innerText()).trim());
  }
  const firstIndustry = page.locator("[data-industry-mapping]").first();
  await firstIndustry.evaluate((element) => element.click());
  await page.waitForTimeout(80);
  const result = await page.evaluate((expected) => {
    const companyDetail = document.querySelector(".detail:not(.industry-detail)");
    const industryDetail = document.querySelector(".industry-detail");
    const bodyText = document.body.innerText;
    return {
      eventId: document.querySelector(".hero .eyebrow")?.textContent.trim().split(" ")[0].toLowerCase(),
      sectionOrder: [...document.querySelectorAll(".section-jumps a")].map((row) => row.textContent.trim()),
      qaTabs: document.querySelectorAll("[data-qa-task]").length,
      timelineNodes: document.querySelectorAll(".timeline-node").length,
      timelineSourceLinks: document.querySelectorAll(".timeline-node a.evidence-link[href^='http']").length,
      timelineText: [...document.querySelectorAll(".timeline-node")].map((row) => row.innerText.trim()),
      calculatedTimelineNodes: [...document.querySelectorAll(".timeline-node")].filter((row) => row.innerText.includes("CALCULATED_ONLY")).length,
      industryCards: document.querySelectorAll("[data-industry-mapping]").length,
      selectedIndustryCompanies: document.querySelectorAll(".company-grid [data-company]").length,
      companyEvidence: companyDetail?.querySelectorAll(".evidence-list .evidence-item").length || 0,
      companyMarketRows: companyDetail?.querySelectorAll(".market-table tbody tr").length || 0,
      industryMechanismNodes: industryDetail?.querySelectorAll(".mechanism-step").length || 0,
      industryMarketRows: industryDetail?.querySelectorAll(".market-table tbody tr").length || 0,
      industryMarketRowTexts: [...(industryDetail?.querySelectorAll(".market-table tbody tr") || [])].map((row) => row.innerText.trim()),
      evidenceLinks: document.querySelectorAll('a.evidence-link[href^="http"]').length,
      causalAbstain: bodyText.includes("ABSTAIN"),
      forbiddenBlocks: ["材料完整性矩阵", "候选概览"].filter((value) => bodyText.includes(value)),
      placeholderText: bodyText.includes("待补充陈述"),
      sectionIdCounts: Object.fromEntries(["overview", "qa", "timeline", "transmission", "industries", "companies"].map((id) => [id, document.querySelectorAll(`#${id}`).length])),
      sectionOrderValid: JSON.stringify([...document.querySelectorAll(".section-jumps a")].map((row) => row.textContent.trim())) === JSON.stringify(expected),
    };
  }, expectedSections);
  result.qaDirectAnswers = qaDirectAnswers;
  result.valid = result.eventId === eventId
    && result.sectionOrderValid
    && result.qaTabs === 4
    && result.timelineNodes === 5
    && result.timelineSourceLinks >= 3
    && result.calculatedTimelineNodes === 2
    && result.qaDirectAnswers.every((value) => value.length >= 100)
    && result.industryCards === 7
    && result.selectedIndustryCompanies === 3
    && result.companyEvidence >= 2
    && result.companyMarketRows === 6
    && result.industryMechanismNodes === 7
    && result.industryMarketRows >= 6
    && result.evidenceLinks >= 1
    && result.causalAbstain
    && result.forbiddenBlocks.length === 0
    && !result.placeholderText
    && Object.values(result.sectionIdCounts).every((count) => count === 1);
  return result;
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", headless: true });
  const errors = [];
  try {
    const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    desktop.on("pageerror", (error) => errors.push(`desktop pageerror: ${error.message}`));
    desktop.on("console", (message) => { if (message.type() === "error") errors.push(`desktop console: ${message.text()}`); });
    await desktop.goto(url, { waitUntil: "networkidle" });
    const navigationIds = await desktop.locator("[data-event]").evaluateAll((rows) => rows.map((row) => row.dataset.event));
    const events = [];
    for (const eventId of newEventIds) events.push(await inspectEvent(desktop, eventId));
    await desktop.locator('[data-event="event-13"]').evaluate((element) => element.click());
    await desktop.waitForTimeout(80);
    const desktopOverflow = await desktop.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    const desktopScreenshot = `${output}/desktop-full.png`;
    await desktop.screenshot({ path: desktopScreenshot, fullPage: true });

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
    mobile.on("pageerror", (error) => errors.push(`mobile pageerror: ${error.message}`));
    mobile.on("console", (message) => { if (message.type() === "error") errors.push(`mobile console: ${message.text()}`); });
    await mobile.goto(url, { waitUntil: "networkidle" });
    await mobile.locator('[data-event="event-13"]').evaluate((element) => element.click());
    await mobile.waitForTimeout(80);
    const mobileOverflow = await mobile.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    const mobileScreenshot = `${output}/mobile-full.png`;
    await mobile.screenshot({ path: mobileScreenshot, fullPage: true });

    const report = {
      url,
      valid: errors.length === 0
        && navigationIds.length === 17
        && navigationIds.every((value, index) => value === `event-${String(index + 1).padStart(2, "0")}`)
        && events.every((row) => row.valid)
        && !desktopOverflow
        && !mobileOverflow,
      errors,
      navigationIds,
      expectedSections,
      events,
      desktopOverflow,
      mobileOverflow,
      screenshots: {
        desktop: { path: desktopScreenshot, sha256: sha256(desktopScreenshot) },
        mobile: { path: mobileScreenshot, sha256: sha256(mobileScreenshot) },
      },
    };
    fs.writeFileSync(`${output}/ui_acceptance_report.json`, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    console.log(JSON.stringify(report));
    if (!report.valid) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error); process.exit(1); });
