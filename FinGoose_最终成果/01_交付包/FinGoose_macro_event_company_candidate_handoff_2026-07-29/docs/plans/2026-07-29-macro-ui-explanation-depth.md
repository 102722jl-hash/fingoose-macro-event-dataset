# Macro UI Explanation Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Subagents are unavailable in this side conversation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand all six macro reasoning steps into concrete Chinese evidence, market observations, analysis opinions, and ex-post validation while fixing the white transmission-channel button.

**Architecture:** Keep the archived JSONL and previous preview versions unchanged. Add a focused Chinese content dictionary, a v11 rendering layer that overrides only the six reasoning-step views, and a thin v11 loader that composes the proven v7/v9/v10 layers with the new renderer.

**Tech Stack:** Static HTML/CSS/JavaScript, JSONL loaded through the existing preview server, Playwright with system Microsoft Edge.

**Repository note:** `D:\桌面\workspace\codex1` is not a Git repository, so commit steps are replaced with explicit browser regression checkpoints.

---

### Task 1: Add a failing six-step content regression

**Files:**
- Create: `.test-tmp/verify-macro-ui-v11-depth.js`

- [ ] **Step 1: Write the failing browser test**

The test opens `http://127.0.0.1:59420/`, selects the first sample, and asserts:

```js
const requiredSections = {
  0: ['来源内容摘要', '能够支持的判断', '证据边界'],
  1: ['预测时可见', '预测时隐藏', '事件后第20个交易日', '仅供事后审计'],
  2: ['事件发生与公开', '经济含义', '市场在前三个交易日的反应'],
  3: ['事件事实', '传导机制', '资产定价验证', '竞争解释'],
  4: ['实际变化', '异常倍数', '逐资产解读', '整体分析观点'],
  5: ['核心观点', '判断依据', '分析观点', '风险与失效条件', '事后验收'],
};
```

It also checks the first `.fact-channel` computed background is not `rgb(240, 240, 240)`, iterates all 40 samples, confirms every step has at least 120 visible characters, verifies no page errors, and checks desktop plus 390px page overflow.

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
$env:TEMP=(Resolve-Path '.test-tmp').Path
$env:TMP=$env:TEMP
node .test-tmp\verify-macro-ui-v11-depth.js
```

Expected: FAIL because the current macro report, cutoff, period, trend, and prediction views lack the required sections, and `.fact-channel` has the browser-default white background.

---

### Task 2: Add the Chinese evidence and event-analysis dictionary

**Files:**
- Create: `.superpowers/brainstorm/side-ui-preview-20260729/content/interactive-dashboard-v11-content.js`

- [ ] **Step 1: Define source summaries for all 10 macro-report evidence records**

Create `reportNarrativeZh` keyed by the evidence IDs used in `forecast_reasoning_chain.macro_report_evidence`:

```js
const reportNarrativeZh = {
  'event01-who-sitrep51': {
    summary: '世界卫生组织第51期疫情报告记录了全球病例与传播范围继续扩大，说明公共卫生冲击已从局部事件演变为全球性风险。',
    support: '支持“全球活动预期走弱、不确定性和流动性需求上升”这一预测前背景。',
    limit: '报告描述疫情扩散，不能单独证明随后每一项市场波动都由疫情定性触发。'
  },
  'event02-eia-steo': {
    summary: '美国能源信息署展望提供事件前原油供需、产量和价格环境，可作为战争升级前的能源市场基线。',
    support: '支持比较事件后油价变化是否超出此前能源基本面所能解释的范围。',
    limit: '基线展望不能预先确认制裁、出口中断或战争持续时间。'
  },
  'event03-mpr': {
    summary: '美联储货币政策报告描述高通胀和金融条件收紧，为一次加息75个基点前的政策环境提供背景。',
    support: '支持市场已关注通胀、政策利率和融资成本的判断。',
    limit: '报告不能单独区分加息决定与同期增长、通胀数据各自造成的行情。'
  },
  'event04-gz-briefing': {
    summary: '政策解读说明优化防控措施对人员流动、生产经营和社会活动恢复的具体影响。',
    support: '支持重新开放可能改善活动与需求预期的传导逻辑。',
    limit: '政策发布不等于经济活动立即完全恢复，短期执行扰动仍可能存在。'
  },
  'event05-fed-joint': {
    summary: '美国金融监管部门联合声明说明了存款保障和紧急稳定安排，反映当局试图阻止银行风险扩散。',
    support: '支持银行压力与政策托底同时影响利率、股票和波动率的判断。',
    limit: '稳定措施可能削弱冲击，不能把所有同期价格变化只归因于银行关闭。'
  },
  'event06-eia-steo': {
    summary: '美国能源信息署展望提供减产宣布前的原油供需和价格基线。',
    support: '支持检验额外减产是否带来超出原有供需预期的价格重定价。',
    limit: '宣布规模不等于最终实际执行量，需求和库存也会影响油价持续性。'
  },
  'event07-eia-steo': {
    summary: '能源展望描述冲突升级附近的原油供需状况，为判断地缘风险溢价提供参照。',
    support: '支持把油价变化拆分为基本面与潜在供应外溢风险。',
    limit: '报告不能证明冲突已经造成实际供应损失。'
  },
  'event08-boj-outlook': {
    summary: '日本央行经济与物价展望提供结束负利率前后的通胀、增长与政策正常化背景。',
    support: '支持利差和日元融资交易可能重新定价的判断。',
    limit: '退出负利率并不等于后续会连续快速加息。'
  },
  'event09-pbc-q2': {
    summary: '中国人民银行货币政策报告提供政策组合出台前的信贷、融资成本和宏观运行基线。',
    support: '支持评估新增金融支持是否改变流动性与风险预期。',
    limit: '政策发布与实体融资需求、市场信心改善之间可能存在时滞。'
  },
  'event10-whitehouse-fact': {
    summary: '美国白宫事实清单说明广泛关税措施、适用范围及其政策理由。',
    support: '支持贸易成本、通胀、增长和报复风险同时进入资产定价的判断。',
    limit: '政策清单不能确定最终执行、豁免、谈判和反制路径。'
  }
};
```

- [ ] **Step 2: Define event-period narratives for all 10 events**

Create `eventPeriodNarrativeZh[eventId]` with `event`, `mechanism`, and `caution` fields. Each entry paraphrases the archived event fact and fact-transmission nodes without introducing facts absent from the dossier.

- [ ] **Step 3: Define helper labels and opinion boundaries**

Add `viewLabelZh`, abnormal-strength thresholds (`abs(score) >= 2` = highly abnormal, `>= 1` = noticeably abnormal, otherwise within ordinary range), and the fixed disclaimer:

```js
const attributionDisclaimerZh = '以下内容是基于时点、异常程度、传导机制和竞争解释形成的证据加权观点，不是严格计量因果结论。';
```

---

### Task 3: Implement the detailed six-step renderer and style fix

**Files:**
- Create: `.superpowers/brainstorm/side-ui-preview-20260729/content/interactive-dashboard-v11-post.js`

- [ ] **Step 1: Add scoped presentation styles**

Inject a `<style>` element defining `.evidence-summary`, `.visible-data`, `.hidden-data`, `.analysis-opinion`, `.audit-warning`, `.deep-table`, and `.fact-channel`. The `.fact-channel` rule must include:

```css
.fact-channel {
  appearance: none;
  width: 100%;
  display: block;
  background: #0a1713;
  color: #edf7f3;
  border: 1px solid #29453a;
  text-align: left;
}
.fact-channel:hover,
.fact-channel:focus-visible {
  background: #10241e;
  border-color: #72efb0;
  outline: 2px solid rgba(114, 239, 176, .35);
}
```

- [ ] **Step 2: Add market-window helpers**

Implement:

```js
function windowsForSample(sample) { /* match sample.market_window_ids */ }
function windowValue(window, code) { /* return date, end value, change, score or null */ }
function strengthZh(score) { /* highly abnormal / noticeable / ordinary */ }
function directionFromChange(change) { /* up / down / flat */ }
function formatMarketObservation(window, code) { /* Chinese sentence with unit */ }
```

All helpers return “未归档” for missing data and never interpolate `undefined`.

- [ ] **Step 3: Render the macro-report step**

For each visible macro report, render source title, publisher, publication time, locator, `reportNarrativeZh.summary`, `support`, and `limit`. Use separate blocks titled “来源内容摘要”, “能够支持的判断”, and “证据边界”.

- [ ] **Step 4: Render the data-cutoff step**

Render a “预测时可见” table containing baseline, D1, and D3 for every target window. Render a separate amber “预测时隐藏” table containing D20 and the warning “预测时不可见，仅供事后审计”. Explain why separating the two prevents future-information leakage.

- [ ] **Step 5: Render the period-description step**

Render “事件发生与公开”, “经济含义”, and “市场在前三个交易日的反应”. The market paragraph is generated from D1/D3 changes for all target windows and includes dates, units, and abnormal-strength interpretations.

- [ ] **Step 6: Render the transmission-chain step**

Reuse the v9 fact chain, but rename section 3 to “资产定价验证”, apply the new dark `.fact-channel` styles, and add a plain-language explanation of why each counterevidence item weakens single-event attribution.

- [ ] **Step 7: Render the trend-confirmation step**

Join each `trend_confirmation.items[]` row with its matching market window. Add columns for expected direction, actual direction, actual change, abnormal score, support result, and “逐资产解读”. Follow the table with “整体分析观点” that identifies cross-asset consistency and the strongest absolute abnormal score.

- [ ] **Step 8: Render the short-term-prediction step**

Render five named sections: “核心观点”, “判断依据”, “分析观点”, “风险与失效条件”, and “事后验收”. The forecast basis uses only baseline/D1/D3; the D20 result appears only inside the ex-post block. Compare forecast direction with D20 change to report directionally correct/incorrect without changing the archived label or confidence.

- [ ] **Step 9: Override `stepText` once**

Store the prior function and route the six known keys to the v11 renderers. Fall back to the prior function for unknown keys. Keep all existing step buttons and event handlers intact.

---

### Task 4: Add the v11 loader and verify GREEN

**Files:**
- Create: `.superpowers/brainstorm/side-ui-preview-20260729/content/interactive-dashboard-v11.html`

- [ ] **Step 1: Create the loader**

Fetch `interactive-dashboard-v7.html`, `interactive-dashboard-v9-post.js`, `interactive-dashboard-v10-post.js`, `interactive-dashboard-v11-content.js`, and `interactive-dashboard-v11-post.js`. Inject `interactive-dashboard-v9-pre.js` in `<head>`, append the four post scripts in version order, and replace the document.

- [ ] **Step 2: Run the v11 depth test**

Run the Task 1 command. Expected: PASS for all 40 samples, all six sections, dark transmission buttons, no errors, and no overflow.

- [ ] **Step 3: Run existing regressions**

Run:

```powershell
node .test-tmp\verify-macro-ui-v8.js
node .test-tmp\verify-macro-ui-left-chinese.js
```

Expected: both exit 0.

- [ ] **Step 4: Capture desktop and mobile screenshots**

Use Playwright at 1440x1000 and 390x844. Save to:

- `.test-tmp/interactive-dashboard-v11-desktop.png`
- `.test-tmp/interactive-dashboard-v11-mobile.png`

- [ ] **Step 5: Open the correct browser URL**

Open `http://localhost:59420/` without query parameters and report that the original JSONL files remain unchanged.
