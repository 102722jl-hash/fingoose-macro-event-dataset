const { chromium } = require("playwright");

const url = process.argv[2];
const output = process.argv[3];
if (!url || !output) {
  throw new Error("usage: node validate_event12_preview.js <url> <output-dir>");
}

async function inspect(page) {
  return page.evaluate(() => {
    const companyDetail = document.querySelector(".detail:not(.industry-detail)");
    const industryDetail = document.querySelector(".industry-detail");
    const points = [...(industryDetail?.querySelectorAll("polyline") || [])].map((row) => row.getAttribute("points") || "");
    const completenessText = document.querySelector(".completeness")?.innerText || "";
    const visibleGapLines = [...new Set(document.body.innerText.split("\n")
      .map((row) => row.trim())
      .filter((row) => /待补|DATA_MISSING|DATA_PENDING|UNKNOWN/.test(row)))];
    return {
      industryCards: document.querySelectorAll(".industry-impact-button").length,
      selectedIndustryCompanies: document.querySelectorAll(".company-button").length,
      companyEvidence: companyDetail?.querySelectorAll(".evidence-list .evidence-item").length || 0,
      companyMarketRows: companyDetail?.querySelectorAll(".market-table tbody tr").length || 0,
      qaCards: document.querySelectorAll(".qa-item").length,
      industryMechanismNodes: industryDetail?.querySelectorAll(".mechanism-step").length || 0,
      industryMarketRows: industryDetail?.querySelectorAll(".market-table tbody tr").length || 0,
      industryPolylines: points.length,
      nonEmptyIndustryPolylines: points.filter((row) => row.trim().length > 0).length,
      continuousPointPairs: points.map((row) => row.trim().split(/\s+/).filter(Boolean).length),
      completeness: {
        evidence42: completenessText.includes("42"),
        companies21: completenessText.includes("21/21"),
        industries7: completenessText.includes("7/7"),
      },
      causalAbstain: document.body.innerText.includes("ABSTAIN"),
      runVisible: document.body.innerText.includes("run-fingoose-event12-gapfill-20260813-001"),
      visibleGapLines,
      viewport: { width: innerWidth, height: innerHeight },
      documentWidth: document.documentElement.scrollWidth,
      pageOverflow: document.documentElement.scrollWidth > innerWidth,
    };
  });
}

async function inspectQaTabs(page) {
  const tasks = ["MAIN_REASONING", "EVIDENCE_AUDIT", "MARKET_VALIDATION", "INDUSTRY_COMPANY"];
  const results = {};
  for (const task of tasks) {
    await page.locator(`[data-qa-task="${task}"]`).click();
    await page.waitForTimeout(50);
    results[task] = await page.evaluate((activeTask) => ({
      active: document.querySelector(`[data-qa-task="${activeTask}"]`)?.classList.contains("active") || false,
      stageReasons: document.querySelectorAll(".qa-stage-reason").length,
      industryImpacts: document.querySelectorAll(".qa-impact").length,
      officialEvidence: document.querySelectorAll(".qa-evidence").length,
      marketResults: document.querySelectorAll(".qa-market-result").length,
      companyResults: document.querySelectorAll(".qa-company-answer").length,
      containsLegacyMissing: /行情窗口为 DATA_MISSING|该阶段推理待补充/.test(document.querySelector(".qa-section")?.innerText || ""),
    }), task);
  }
  await page.locator('[data-qa-task="MAIN_REASONING"]').click();
  return results;
}

async function main() {
  const browser = await chromium.launch({ executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", headless: true });
  const errors = [];
  try {
    const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    desktop.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
    desktop.on("console", (message) => {
      if (message.type() === "error") errors.push(`console: ${message.text()}`);
    });
    await desktop.goto(url, { waitUntil: "networkidle" });
    await desktop.locator(".industry-impact-button").first().click();
    await desktop.waitForTimeout(100);
    const desktopResult = await inspect(desktop);
    desktopResult.qaTabs = await inspectQaTabs(desktop);
    await desktop.screenshot({ path: `${output}/desktop-full.png`, fullPage: true });

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
    mobile.on("pageerror", (error) => errors.push(`mobile pageerror: ${error.message}`));
    mobile.on("console", (message) => {
      if (message.type() === "error") errors.push(`mobile console: ${message.text()}`);
    });
    await mobile.goto(url, { waitUntil: "networkidle" });
    await mobile.locator(".industry-impact-button").first().click();
    await mobile.waitForTimeout(100);
    const mobileResult = await inspect(mobile);
    await mobile.screenshot({ path: `${output}/mobile-full.png`, fullPage: true });

    const result = { url, errors, desktop: desktopResult, mobile: mobileResult };
    const assertions = [
      errors.length === 0,
      desktopResult.industryCards === 7,
      desktopResult.selectedIndustryCompanies === 3,
      desktopResult.companyEvidence === 2,
      desktopResult.companyMarketRows === 6,
      desktopResult.qaCards === 4,
      desktopResult.industryMechanismNodes === 7,
      desktopResult.industryMarketRows === 6,
      desktopResult.industryPolylines >= 2,
      desktopResult.nonEmptyIndustryPolylines === desktopResult.industryPolylines,
      desktopResult.continuousPointPairs.every((count) => count >= 20),
      Object.values(desktopResult.completeness).every(Boolean),
      desktopResult.causalAbstain && desktopResult.runVisible,
      Object.values(desktopResult.qaTabs).every((row) => row.active && !row.containsLegacyMissing),
      desktopResult.qaTabs.MAIN_REASONING.stageReasons === 3,
      desktopResult.qaTabs.MAIN_REASONING.industryImpacts === 7,
      desktopResult.qaTabs.EVIDENCE_AUDIT.officialEvidence >= 1,
      desktopResult.qaTabs.MARKET_VALIDATION.marketResults === 7,
      desktopResult.qaTabs.INDUSTRY_COMPANY.companyResults === 21,
      !desktopResult.visibleGapLines.some((row) => /行情窗口为 DATA_MISSING|M3\s+数据待补|图表数据待补|混杂、竞争解释与反证待补|该阶段推理待补充/.test(row)),
      !desktopResult.pageOverflow && !mobileResult.pageOverflow,
    ];
    result.valid = assertions.every(Boolean);
    const serialized = `${JSON.stringify(result, null, 2)}\n`;
    require("fs").writeFileSync(`${output}/ui_runtime_validation.json`, serialized, "utf8");
    console.log(serialized);
    if (!result.valid) process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
