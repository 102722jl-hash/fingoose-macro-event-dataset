import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.argv[2];
const output = process.argv[3];
const previewDir = process.argv[4];
const run = path.join(root, "work", "skill_research_runs", "run-fingoose-final-004");
const replay = path.join(run, "replay-1");

const readJson = async (p) => JSON.parse(await fs.readFile(p, "utf8"));
const lines = (await fs.readFile(path.join(replay, "candidate_master_data.jsonl"), "utf8"))
  .split(/\r?\n/).filter(Boolean).map(JSON.parse);
const validation = await readJson(path.join(replay, "validation_report.json"));
const repro = await readJson(path.join(run, "reproducibility_report.json"));

const seriesZh = {
  SP500: "标普500", VIXCLS: "VIX波动率指数", DCOILWTICO: "WTI原油",
  DCOILBRENTEU: "布伦特原油", DGS10: "美国10年期国债收益率",
  DTWEXBGS: "美元广义指数", DEXCHUS: "美元兑人民币", DEXJPUS: "美元兑日元",
};

const wb = Workbook.create();
wb.comments.setSelf({ displayName: "User" });
const overview = wb.worksheets.add("汇报总览");
const events = wb.worksheets.add("十事件明细");
const market = wb.worksheets.add("锚定物行情");
const files = wb.worksheets.add("数据文件索引");

const navy = "#16324F", blue = "#2E74B5", pale = "#E8EEF5", gold = "#FFF2CC";
const dark = "#1F2937", grid = "#D8DEE8", white = "#FFFFFF";

function title(sheet, range, text, subtitle) {
  sheet.mergeCells(range);
  const start = range.split(":")[0];
  sheet.getRange(start).values = [[text]];
  sheet.getRange(range).format = { fill: navy, font: { color: white, bold: true, size: 18 }, verticalAlignment: "center" };
  const row = Number(start.match(/\d+/)[0]) + 1;
  const cols = range.match(/[A-Z]+/g);
  sheet.mergeCells(`${cols[0]}${row}:${cols[1]}${row}`);
  sheet.getRange(`${cols[0]}${row}`).values = [[subtitle]];
  sheet.getRange(`${cols[0]}${row}:${cols[1]}${row}`).format = { fill: "#F4F6F9", font: { color: "#5B6573", italic: true, size: 10 }, verticalAlignment: "center", wrapText: true };
  sheet.getRange("1:1").format.rowHeight = 42;
  sheet.getRange("2:2").format.rowHeight = 28;
}

function styleHeader(sheet, range) {
  sheet.getRange(range).format = {
    fill: pale, font: { bold: true, color: navy }, verticalAlignment: "center",
    horizontalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: grid },
  };
}

function styleBody(sheet, range) {
  sheet.getRange(range).format = {
    font: { color: dark, size: 10 }, verticalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: grid },
  };
}

function setWidths(sheet, widths) {
  for (const [col, width] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidth = width;
}

const milestoneCount = lines.reduce((a, x) => a + x.event.milestones.length, 0);
const industryCount = lines.reduce((a, x) => a + x.industries.length, 0);
const companyCount = lines.reduce((a, x) => a + x.companies.length, 0);
const qaCount = lines.reduce((a, x) => a + x.qa.length, 0);
const marketCount = lines.reduce((a, x) => a + x.event.market_windows.length, 0);

title(overview, "A1:F1", "FinGoose 宏观事件研究数据阶段成果", "截至 2026-08-12｜仅汇总已有完成内容，不包含新增实时研究");
overview.getRange("A4:C4").values = [["成果项", "完成量", "汇报说明"]];
const summary = [
  ["宏观母事件", lines.length, "10 个统一事件包"],
  ["候选样本", validation.counts.sft_samples, "事件、行业、公司、问答四类"],
  ["事件里程碑", milestoneCount, "前置条件、初始冲击及后续节点"],
  ["行业影响分析", industryCount, "每事件 7-9 个行业"],
  ["公司影响分析", companyCount, "每事件 3 家事前暴露公司"],
  ["事件关联问答", qaCount, "每事件 4 类关联问答"],
  ["核心行情窗口", marketCount, "每事件 4 个价值锚定物"],
  ["闭环推理链", validation.closure_reason_stats.CLOSED, "开放链为 0"],
];
overview.getRange(`A5:C${4 + summary.length}`).values = summary;
styleHeader(overview, "A4:C4"); styleBody(overview, `A5:C${4 + summary.length}`);
overview.getRange("E4:F4").values = [["质量指标", "结果"]];
const quality = [
  ["机器验证", `${validation.errors.length} errors / ${validation.warnings.length} warnings`],
  ["完整阶段分析", `${validation.content_quality_stats.complete_horizon_count}/157`],
  ["占位样本", validation.content_quality_stats.placeholder_sample_count],
  ["离线复现", repro.stable ? "稳定，双轮 SHA 一致" : "未通过"],
  ["网络访问", repro.network_accessed ? "是" : "否"],
  ["研究文字重生成", repro.prose_regenerated ? "是" : "否"],
];
overview.getRange("E5:F10").values = quality;
styleHeader(overview, "E4:F4"); styleBody(overview, "E5:F10");
overview.mergeCells("A15:F15");
overview.getRange("A15").values = [["建议汇报口径：已完成十个宏观事件从事实、推理、行业公司传导到 D20/M3 行情验证的候选数据建设；当前进入人工研究审核和正式准入阶段。"]];
overview.getRange("A15:F15").format = { fill: gold, font: { bold: true, color: "#7A5A00", size: 11 }, wrapText: true, verticalAlignment: "center", borders: { preset: "outside", style: "thin", color: "#D6B656" } };
overview.mergeCells("A17:F18");
overview.getRange("A17").values = [["边界：所有记录保持 NEEDS_HUMAN_REVIEW、formal_ready=false；行情只能验证窗口表现和机制一致性，不能单独证明宏观事件因果；当前未执行真实 GPU/QLoRA 训练。"]];
overview.getRange("A17:F18").format = { fill: "#F4F6F9", font: { color: dark, size: 10 }, wrapText: true, verticalAlignment: "center" };
setWidths(overview, { A: 21, B: 13, C: 36, D: 3, E: 23, F: 28 });
overview.getRange("15:15").format.rowHeight = 48;
overview.showGridLines = false; overview.freezePanes.freezeRows(3);

title(events, "A1:J1", "十个宏观事件覆盖明细", "数量与内容直接取自 candidate_master_data.jsonl");
const eventHeaders = ["事件ID", "事件名称", "里程碑", "行业", "公司", "问答", "核心锚定物", "公司范围", "审核状态", "正式可用"];
events.getRange("A4:J4").values = [eventHeaders];
const eventRows = lines.map(x => [
  x.event_id, x.event.title_zh, x.event.milestones.length, x.industries.length, x.companies.length, x.qa.length,
  x.event.market_windows.map(w => `${seriesZh[w.series_id] ?? w.series_id}(${w.series_id})`).join("、"),
  x.companies.map(c => `${c.company_name} ${c.company_code}`).join("、"),
  x.research_content.review_state.review_status,
  x.research_content.review_state.formal_ready ? "是" : "否",
]);
events.getRange(`A5:J${4 + eventRows.length}`).values = eventRows;
styleHeader(events, "A4:J4"); styleBody(events, `A5:J${4 + eventRows.length}`);
events.getRange("C5:F14").format.horizontalAlignment = "center";
events.getRange("J5:J14").format.fill = "#FCE8E6";
setWidths(events, { A: 12, B: 28, C: 9, D: 8, E: 8, F: 8, G: 48, H: 45, I: 24, J: 12 });
events.getRange("4:4").format.rowHeight = 30; events.getRange("5:14").format.rowHeight = 55;
events.showGridLines = false; events.freezePanes.freezeRows(4); events.freezePanes.freezeColumns(2);

title(market, "A1:P1", "价值锚定物行情验证", "T-1 为事件前基准；D1/D3/D5/D20/M3 均为事后实际行情，不代表因果识别");
const marketHeaders = ["事件ID", "事件名称", "序列", "锚定物", "指标口径", "T-1日期", "T-1值", "D1%/bp", "D3%/bp", "D5%/bp", "D20%/bp", "M3%/bp", "D20日期", "M3日期", "混杂等级", "因果边界"];
market.getRange("A4:P4").values = [marketHeaders];
const marketRows = [];
for (const x of lines) {
  for (const w of x.event.market_windows) {
    const ws = w.windows;
    marketRows.push([
      x.event_id, x.event.title_zh, w.series_id, seriesZh[w.series_id] ?? w.series_id, w.metric_type,
      w.baseline.date, w.baseline.value, ws.D1.raw_change, ws.D3.raw_change, ws.D5.raw_change, ws.D20.raw_change, ws.M3.raw_change,
      ws.D20.date, ws.M3.date, w.confounder_level, "仅验证表现或机制一致性；不单独证明因果",
    ]);
  }
}
market.getRange(`A5:P${4 + marketRows.length}`).values = marketRows;
styleHeader(market, "A4:P4"); styleBody(market, `A5:P${4 + marketRows.length}`);
market.getRange(`F5:F${4 + marketRows.length}`).format.numberFormat = "yyyy-mm-dd";
market.getRange(`M5:N${4 + marketRows.length}`).format.numberFormat = "yyyy-mm-dd";
market.getRange(`G5:L${4 + marketRows.length}`).format.numberFormat = "0.00";
market.getRange(`H5:L${4 + marketRows.length}`).conditionalFormats.add("colorScale", { colors: ["#F8696B", "#FFEB84", "#63BE7B"], thresholds: ["min", "50%", "max"] });
setWidths(market, { A: 12, B: 28, C: 18, D: 25, E: 20, F: 13, G: 12, H: 12, I: 12, J: 12, K: 12, L: 12, M: 13, N: 13, O: 14, P: 38 });
market.getRange("4:4").format.rowHeight = 34; market.getRange(`5:${4 + marketRows.length}`).format.rowHeight = 32;
market.showGridLines = false; market.freezePanes.freezeRows(4); market.freezePanes.freezeColumns(4);

title(files, "A1:F1", "交付数据文件索引", "黄金复现目录：run-fingoose-final-004 / replay-1");
files.getRange("A4:F4").values = [["用途", "文件", "相对路径", "大小(MB)", "SHA256", "说明"]];
const fileDefs = [
  ["全量统一主数据", "candidate_master_data.jsonl", path.join("replay-1", "candidate_master_data.jsonl"), "10 个事件完整候选包"],
  ["训练候选数据", "candidate_sft_dataset.jsonl", path.join("replay-1", "candidate_sft_dataset.jsonl"), "157 条 SFT 候选样本"],
  ["数据拆分清单", "split_manifest.json", path.join("replay-1", "split_manifest.json"), "按事件隔离 train/validation/test"],
  ["机器验证报告", "validation_report.json", path.join("replay-1", "validation_report.json"), "0 errors / 0 warnings"],
  ["离线复现报告", "reproducibility_report.json", "reproducibility_report.json", "双轮 SHA 一致"],
];
const fileRows = [];
for (const [purpose, name, rel, note] of fileDefs) {
  const abs = path.join(run, rel);
  const bytes = await fs.readFile(abs);
  fileRows.push([purpose, name, rel.replaceAll("\\", "/"), bytes.length / 1024 / 1024, crypto.createHash("sha256").update(bytes).digest("hex").toUpperCase(), note]);
}
files.getRange("A5:F9").values = fileRows;
styleHeader(files, "A4:F4"); styleBody(files, "A5:F9");
files.getRange("D5:D9").format.numberFormat = "0.00";
setWidths(files, { A: 21, B: 34, C: 40, D: 12, E: 72, F: 34 });
files.getRange("4:4").format.rowHeight = 30; files.getRange("5:9").format.rowHeight = 44;
files.showGridLines = false; files.freezePanes.freezeRows(4);

await fs.mkdir(path.dirname(output), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
for (const sheetName of ["汇报总览", "十事件明细", "锚定物行情", "数据文件索引"]) {
  const preview = await wb.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const inspectOverview = await wb.inspect({ kind: "table", range: "汇报总览!A1:F18", include: "values,formulas", tableMaxRows: 20, tableMaxCols: 8, maxChars: 5000 });
const inspectErrors = await wb.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan", maxChars: 2500 });
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(output);
console.log(JSON.stringify({ output, sheets: 4, eventRows: eventRows.length, marketRows: marketRows.length, overviewInspect: inspectOverview.ndjson, errorScan: inspectErrors.ndjson }, null, 2));
