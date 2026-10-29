"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const state = {
  overview: null,
  events: [],
  workspace: null,
  market: null,
  company: null,
  reviews: [],
  eventId: "",
  marketId: "",
  dossierId: "",
  stepIndex: 0,
  controllers: new Map(),
};

const labels = {
  MACRO_REPORT: "宏观研报",
  DATA: "数据截止",
  PERIOD_DESCRIPTION: "期间描述",
  FACT_TRANSMISSION_CHAIN: "事实传导链",
  MULTI_DATA_TREND_CONFIRMATION: "多重趋势确认",
  SHORT_TERM_PREDICTION: "短期预测",
  MAJOR_EVENT: "重大事件",
  INDUSTRY_MACRO_VARIABLE: "行业 / 宏观变量",
  COMPANY_BUSINESS_EXPOSURE: "公司业务暴露",
  OPERATING_METRIC: "经营指标",
  FINANCIAL_RESULT: "财务结果",
  COMPETING_EXPLANATION: "竞争解释",
  ATTRIBUTION_OR_FORECAST: "关联判断 / 短期预测",
  VERIFIED_EVIDENCE: "已验证",
  VENDOR_VERIFIED: "供应商已核验",
  PARTIAL_EVIDENCE: "部分证据",
  PENDING_EVIDENCE: "待补证",
  SECOND_REVIEW_REQUIRED: "待复审",
  AI_INITIAL_REVIEW_COMPLETED: "初审完成",
  VERIFIED: "已验证",
  REJECTED: "已拒绝",
  PRIMARY_DRIVER: "主要驱动因素",
  CONTRIBUTING_FACTOR: "贡献因素",
  VERIFIED_ASSOCIATION: "已验证关联",
  CONTRIBUTING_ASSOCIATION: "贡献关联",
  WEAK_RELATION: "弱关联",
  UNSUPPORTED: "不支持",
  PENDING_ASSESSMENT: "待判断",
  UP: "上升",
  DOWN: "下降",
  MIXED: "混合",
  UNCERTAIN: "不确定",
  HIGH: "高",
  MEDIUM: "中",
  LOW: "低",
  UNKNOWN: "未知",
  INCONCLUSIVE: "无法判断",
  FORMAL: "正式归档",
  CANDIDATE: "候选版",
  APPROVED: "已通过",
  SUPPORTS: "支持传导判断",
  CONTRADICTS: "与传导判断矛盾",
  NEUTRAL: "中性",
  SUPPORTED: "有证据支持",
  STRONG: "强",
  LIMITED: "有限",
  CONTRADICTED: "存在矛盾",
  RISK_APPETITE: "风险偏好",
  GLOBAL_DEMAND: "全球需求",
  LIQUIDITY_STRESS: "流动性压力",
  ENERGY_SUPPLY: "能源供给",
  INFLATION_EXPECTATIONS: "通胀预期",
  MONETARY_POLICY: "货币政策",
  single_asset_attribution_forecast: "单资产归因与预测",
  cross_asset_attribution_forecast: "跨资产归因与预测",
  COMPANY_ATTRIBUTION: "公司事后归因",
  COMPANY_FORECAST: "公司事前预测",
  REVENUE: "营业收入",
  GROSS_MARGIN: "毛利率",
  NET_PROFIT: "归母净利润",
  OPERATING_CASH_FLOW: "经营活动现金流",
  REVENUE_MOMENTUM: "收入动量",
  PROFIT_STATE: "利润状态",
  CNY_million: "百万元",
  CNY_10_thousand: "万元",
  cumulative_difference: "季度累计值差分",
  COMPANY_EVIDENCE_INCOMPLETE: "公司证据尚未补齐",
  PRICE_WINDOWS_PENDING: "个股与指数行情窗口待归档",
  FORMAL_REVIEWS_INCOMPLETE: "正式复审尚未完成",
  TWENTY_SEVEN_COMPANIES_REQUIRE_OFFICIAL_ARCHIVES: "仍有 27 家公司缺少官方材料归档",
  LOW_CONFIDENCE: "低置信度",
  STRONG_COMPETING_EXPLANATION: "强竞争解释",
  CORE_DIMENSION_CONTRADICTED: "核心维度存在矛盾",
  CORE_DIMENSION_UNKNOWN: "核心维度未知",
  EVENT_CHANNEL_NOT_EXPLICITLY_DISCLOSED: "公司未明确披露事件传导渠道",
  QUARTERLY_CUMULATIVE_DIFFERENCE: "季度累计值差分",
  abnormal_movement: "异常程度",
  competing_explanations: "竞争解释",
  temporal_alignment: "时点吻合",
  transmission_mechanism: "传导机制",
  SP500: "标普 500 指数",
  VIXCLS: "CBOE 市场波动率指数",
  DCOILWTICO: "WTI 原油现货价格",
  DCOILBRENTEU: "布伦特原油现货价格",
  DEXCHUS: "美元兑人民币汇率",
  DGS10: "美国 10 年期国债收益率",
  USDJPY: "美元兑日元汇率",
  SSECOMP: "上证综指",
  CSI300: "沪深 300 指数",
  ACCELERATE: "加速",
  STABLE: "稳定",
  DECELERATE: "减速",
  IMPROVE: "改善",
  DETERIORATE: "恶化",
  LOSS: "亏损",
  event: "事件事实",
  mechanism: "经济传导机制",
  market: "市场结果",
  COMPANY_STOCK_WINDOW: "个股与沪深 300 行情窗口",
};

const ZH_TEXT = {
  "WHO characterizes COVID-19 as a global pandemic": "世界卫生组织将 COVID-19 定性为全球大流行",
  "Russia's full-scale attack on Ukraine": "俄罗斯对乌克兰发动全面军事进攻",
  "Federal Reserve raises rates by 75 basis points": "美联储加息 75 个基点",
  "China releases ten optimized COVID-control measures": "中国发布优化疫情防控“新十条”",
  "Silicon Valley Bank closes and authorities stabilize the system": "硅谷银行关闭，监管部门采取紧急稳定措施",
  "OPEC+ members announce additional voluntary production cuts": "OPEC+ 成员宣布额外自愿减产",
  "Middle East conflict escalates on 7 October 2023": "2023 年 10 月 7 日中东冲突升级",
  "Bank of Japan ends negative interest rates": "日本央行结束负利率政策",
  "China announces a broad financial support policy package": "中国发布一揽子金融支持政策",
  "United States announces broad reciprocal tariff measures": "美国宣布广泛的对等关税措施",
  "The report documented expanding global cases and transmission.": "报告记录了全球病例增加和传播范围扩大的事实。",
  "The outlook supplies the pre-event energy baseline.": "该展望提供了事件发生前的能源市场基线。",
  "The report describes inflation and tighter financial conditions.": "报告描述了通胀和金融条件收紧的背景。",
  "The briefing describes mobility and activity changes.": "发布会说明了人员流动和经济活动的变化。",
  "The statement describes emergency stabilization measures.": "声明说明了紧急稳定金融体系的措施。",
  "The outlook supplies the pre-cut oil baseline.": "该展望提供了减产宣布前的原油市场基线。",
  "The report describes oil conditions by the D3 cutoff.": "报告说明了截至 D3 截止时点的原油市场状况。",
  "The outlook supplies the policy-normalization baseline.": "该展望提供了政策正常化前的经济与价格基线。",
  "The report supplies the pre-package macro and credit baseline.": "报告提供了政策组合发布前的宏观和信贷基线。",
  "The fact sheet describes the measures and transmission logic.": "事实清单说明了关税措施及其可能的传导逻辑。",
  "The first three tradable sessions after WHO's pandemic characterization.": "世卫组织作出全球大流行定性后的前三个可交易日。",
  "The first three tradable sessions after the full-scale attack.": "全面军事进攻发生后的前三个可交易日。",
  "The first three tradable sessions after the rate increase.": "加息决定公布后的前三个可交易日。",
  "The first three tradable sessions after the optimized measures.": "优化疫情防控措施发布后的前三个可交易日。",
  "The first three tradable sessions after closure and weekend response.": "硅谷银行关闭及周末稳定措施后的前三个可交易日。",
  "The first three tradable sessions after the cut announcement.": "减产公告后的前三个可交易日。",
  "The first three tradable sessions after the escalation.": "冲突升级后的前三个可交易日。",
  "The first three tradable sessions after the framework change.": "日本央行政策框架调整后的前三个可交易日。",
  "The first three tradable sessions after the support package.": "金融支持政策组合发布后的前三个可交易日。",
  "The first three tradable sessions after the tariff announcement.": "关税措施宣布后的前三个可交易日。",
  "WHO characterized COVID-19 as a pandemic.": "世卫组织将 COVID-19 定性为全球大流行。",
  "Expected activity weakened while uncertainty and liquidity demand rose.": "经济活动预期走弱，同时不确定性和流动性需求上升。",
  "Equities, volatility, oil and the renminbi repriced the risk-off shock.": "股票、波动率、原油和人民币对避险冲击重新定价。",
  "Russia launched a full-scale attack on Ukraine.": "俄罗斯对乌克兰发动全面军事进攻。",
  "Energy supply risk and sanctions raised inflation and risk premia.": "能源供应风险和制裁预期推高通胀与风险溢价。",
  "Oil, volatility, equities and the renminbi repriced.": "原油、波动率、股票和人民币出现重新定价。",
  "The FOMC raised rates by 75 basis points.": "美联储公开市场委员会加息 75 个基点。",
  "Yields, discount rates and dollar demand repriced.": "国债收益率、贴现率和美元需求重新定价。",
  "Yields, equities, dollar and renminbi tested the channel.": "国债收益率、股票、美元和人民币共同检验该传导渠道。",
  "China released ten optimized measures.": "中国发布优化疫情防控“新十条”。",
  "Reopening expectations improved mobility and demand.": "重新开放预期改善人员流动和需求预期。",
  "Equities, oil, volatility and renminbi repriced.": "股票、原油、波动率和人民币出现重新定价。",
  "SVB closed and authorities responded.": "硅谷银行关闭，监管部门随后采取应对措施。",
  "Bank stress raised safe-haven demand and lowered rate expectations.": "银行业压力提高避险需求，并压低利率预期。",
  "Equities, yields, volatility and renminbi repriced.": "股票、国债收益率、波动率和人民币出现重新定价。",
  "OPEC+ members announced cuts.": "OPEC+ 成员宣布减产。",
  "Expected supply tightened and inflation risk rose.": "预期供给收紧，通胀风险上升。",
  "Oil, equities and renminbi repriced.": "原油、股票和人民币出现重新定价。",
  "Conflict escalated sharply.": "冲突显著升级。",
  "Spillover risk raised energy and safe-haven premia.": "外溢风险推高能源和避险资产溢价。",
  "The BOJ ended negative rates.": "日本央行结束负利率政策。",
  "Japanese rate differentials and funding trades repriced.": "日本利差和融资套利交易重新定价。",
  "Yen, yields, equities and renminbi repriced.": "日元、国债收益率、股票和人民币出现重新定价。",
  "Authorities announced broad financial support.": "有关部门宣布广泛的金融支持措施。",
  "Liquidity, financing costs and risk expectations improved.": "流动性、融资成本和风险预期改善。",
  "Renminbi, equities, yields and dollar repriced.": "人民币、股票、国债收益率和美元出现重新定价。",
  "The United States announced broad tariffs.": "美国宣布广泛关税措施。",
  "Trade costs, growth, inflation and retaliation risks repriced.": "贸易成本、增长、通胀和报复性措施风险重新定价。",
  "Equities, yields, dollar and renminbi repriced.": "股票、国债收益率、美元和人民币出现重新定价。",
  "NATO documented the large-scale attack and escalation.": "北约文件记录了大规模进攻及局势升级。",
  "The FOMC announced a 75 basis point increase.": "美联储公开市场委员会宣布加息 75 个基点。",
  "The official page records release of ten optimized measures.": "官方页面记录了优化疫情防控“新十条”的发布。",
  "FDIC records the closure and receivership.": "美国联邦存款保险公司记录了银行关闭及接管。",
  "OPEC documented additional voluntary production cuts.": "OPEC 文件记录了额外自愿减产安排。",
  "The same-day UN statement documents the attacks and escalation.": "联合国当日声明记录了袭击及局势升级。",
  "The BOJ ended the negative short-rate setting.": "日本央行结束负短期政策利率设置。",
  "The briefing announced monetary, housing and market support.": "发布会宣布了货币、房地产和资本市场支持措施。",
  "The order established a broad reciprocal tariff framework.": "行政令建立了广泛的对等关税框架。",
  "No archived official company disclosure currently verifies the candidate business exposure.": "尚未归档可验证该候选业务暴露的公司官方披露。",
  "No archived official company evidence currently supports a comparable operating metric.": "尚未归档可支持可比经营指标的公司官方证据。",
  "No archived official company reports currently support standalone-quarter financial results.": "尚未归档可支持单季度财务结果的公司官方报告。",
  "No archived company-specific evidence currently supports a competing explanation assessment.": "尚未归档可支持竞争解释判断的公司特定证据。",
  "Attribution and forecast labels remain unknown until company evidence and independent review exist.": "在公司证据和独立复审完成前，归因与预测标签保持未知。",
  "No archived auditable company and CSI 300 price series is available; returns remain unknown.": "尚无可审计的个股与沪深 300 行情归档，因此收益率保持未知。",
};

const SOURCE_TITLES_ZH = {
  "WHO opening remarks, 11 March 2020": "世卫组织 2020 年 3 月 11 日开场讲话",
  "COVID-19 Situation Report 51": "COVID-19 第 51 期形势报告",
  "North Atlantic Council statement on Russia's attack": "北大西洋理事会关于俄罗斯进攻的声明",
  "Short-Term Energy Outlook, February 2022": "2022 年 2 月短期能源展望",
  "FOMC statement, June 2022": "美联储 2022 年 6 月议息声明",
  "Monetary Policy Report, June 2022": "2022 年 6 月货币政策报告",
  "Official interpretation of the ten measures": "优化疫情防控“新十条”官方解读",
  "Implementation briefing on the ten measures": "“新十条”实施情况发布会",
  "Silicon Valley Bank failure information": "硅谷银行关闭与接管信息",
  "Joint banking-system stabilization statement": "银行体系稳定措施联合声明",
  "Voluntary production adjustments": "自愿产量调整声明",
  "Short-Term Energy Outlook, March 2023": "2023 年 3 月短期能源展望",
  "UN Special Coordinator statement, 7 October 2023": "联合国特别协调员 2023 年 10 月 7 日声明",
  "Short-Term Energy Outlook, October 2023": "2023 年 10 月短期能源展望",
  "Changes in the Monetary Policy Framework": "日本央行货币政策框架调整",
  "Outlook for Economic Activity and Prices, January 2024": "2024 年 1 月经济活动与价格展望",
  "Briefing on financial support for high-quality development": "金融支持经济高质量发展发布会",
  "China Monetary Policy Report, 2024 Q2": "中国货币政策执行报告（2024 年第二季度）",
  "Executive order regulating imports with reciprocal tariffs": "以对等关税调节进口的行政令",
  "Fact sheet on reciprocal tariffs": "对等关税事实清单",
};

const ANALYSIS_TEXT_ZH = {
  "Oil-market stress also affected equities.": "原油市场压力也会影响股票，因此股市波动不能只归因于疫情事件。",
  "Volatility was already elevated.": "事件前市场波动率已经处于高位。",
  "The oil price war is a strong competitor.": "同期原油价格战是一个强竞争解释。",
  "Oil supply conflict complicates common-shock attribution.": "原油供给冲突使跨资产共同冲击的归因更复杂。",
  "Energy balances were already tight.": "事件前能源供需平衡已经偏紧。",
  "Tightening expectations also raised volatility.": "货币紧缩预期也会推高市场波动。",
  "Fed repricing and reversal complicate attribution.": "美联储预期的重新定价与反转使归因更复杂。",
  "Monetary repricing competes.": "货币政策重新定价构成竞争解释。",
  "Inflation data already moved yields.": "通胀数据此前已经推动国债收益率变化。",
  "Recession fears also mattered.": "经济衰退担忧也是重要影响因素。",
  "Foreign tightening and positioning compete.": "海外紧缩政策和市场仓位变化构成竞争解释。",
  "Inflation and growth news compete.": "同期通胀与增长消息构成竞争解释。",
  "Fed expectations also mattered.": "美联储政策预期也产生了影响。",
  "Supply policy also moved oil.": "供给政策也推动了油价变化。",
  "U.S. policy is a stronger direct driver.": "美国政策是更直接、更强的驱动因素。",
  "Global drivers dominate parts of the panel.": "部分市场序列主要由全球性因素主导。",
  "Stabilization limited the response.": "稳定措施限制了市场冲击幅度。",
  "Inflation data also moved rates.": "通胀数据也推动了利率变化。",
  "Lower rates can offset contagion risk.": "利率下降可能抵消金融风险传染的影响。",
  "Risk and rate channels offset.": "风险渠道与利率渠道可能相互抵消。",
  "Demand affects persistence.": "需求变化会影响冲击的持续性。",
  "Inventories affect WTI.": "库存变化会直接影响 WTI 原油价格。",
  "Rate and sector news dominate.": "利率和行业消息可能是主要驱动因素。",
  "Only oil is directly exposed.": "在该组资产中只有原油具有直接暴露。",
  "No immediate supply loss was established.": "当时尚未证实出现即时供应损失。",
  "U.S. rates also moved volatility.": "美国利率变化也推动了波动率。",
  "Yields and U.S. data compete.": "国债收益率和美国经济数据构成竞争解释。",
  "Supply and yield signals are mixed.": "供给与收益率信号相互混杂。",
  "Dovish guidance offsets the signal.": "偏鸽派指引会抵消政策变化信号。",
  "Fed guidance is more direct.": "美联储指引是更直接的驱动因素。",
  "Fed and earnings dominate.": "美联储政策和企业盈利因素占主导。",
  "BOJ and Fed signals conflict.": "日本央行与美联储信号存在冲突。",
  "Lower rates can weaken currency.": "较低利率也可能导致本币走弱。",
  "Fed easing also moved equities.": "美联储宽松预期也推动了股票市场。",
  "Fed and U.S. data dominate.": "美联储政策和美国经济数据占主导。",
  "U.S. policy remains a common driver.": "美国政策仍然是跨资产共同驱动因素。",
  "Positioning affected the opening move.": "市场仓位影响了开盘阶段的波动。",
  "Tariff inflation pushes the other way.": "关税引发的通胀压力会推动相反方向的变化。",
  "U.S. growth damage can weaken dollar.": "美国增长受损可能导致美元走弱。",
  "Growth and inflation imply conflicting rates.": "增长与通胀因素对利率方向给出冲突信号。",
  "Stabilization measures reverse risk-off trading.": "若稳定措施使避险交易反转，则预测失效。",
  "Implied volatility normalizes.": "若隐含波动率恢复常态，则预测失效。",
  "Supply coordination offsets demand loss.": "若供给协调抵消需求下降，则预测失效。",
  "Cross-asset confirmation breaks down.": "若跨资产一致性消失，则预测失效。",
  "Exports remain fully available.": "若相关出口保持完全可用，则供应冲击判断失效。",
  "Conflict containment reduces tail risk.": "若冲突得到控制并降低尾部风险，则预测失效。",
  "Policy expectations dominate risk.": "若政策预期取代风险因素成为主导，则预测失效。",
  "Supply risk recedes.": "若供给风险消退，则预测失效。",
  "Growth concerns dominate.": "若增长担忧占主导，则原方向预测失效。",
  "Guidance is less restrictive.": "若政策指引没有预期中严格，则预测失效。",
  "Foreign rates rise faster.": "若海外利率上升更快，则相对利差预测失效。",
  "Growth shock lowers yields.": "若增长冲击压低收益率，则原预测失效。",
  "Reopening disruption dominates.": "若重新开放过程中的扰动占主导，则预测失效。",
  "China demand fails to improve.": "若中国需求未改善，则预测失效。",
  "Global uncertainty rises.": "若全球不确定性继续上升，则预测失效。",
  "Confirmation stays mixed.": "若多市场确认持续混合，则预测可信度下降。",
  "Contagion concerns subside.": "若风险传染担忧消退，则预测失效。",
  "Inflation dominates stress.": "若通胀因素压过金融压力，则利率预测失效。",
  "Easier rates dominate.": "若利率宽松效应占主导，则原预测失效。",
  "Confidence returns quickly.": "若市场信心快速恢复，则预测失效。",
  "Cuts are not implemented.": "若减产未实际执行，则预测失效。",
  "Inventories offset the signal.": "若库存变化抵消供应信号，则预测失效。",
  "Energy gains offset pressure.": "若能源收益抵消成本压力，则预测失效。",
  "Oil confirmation reverses.": "若油价确认信号反转，则预测失效。",
  "Conflict remains contained.": "若冲突保持局部化，则外溢预测失效。",
  "Escalation risk falls.": "若冲突升级风险下降，则预测失效。",
  "Lower yields offset risk.": "若收益率下降抵消风险冲击，则预测失效。",
  "Oil premium reverses.": "若原油风险溢价反转，则预测失效。",
  "Further tightening expectations fall.": "若进一步紧缩预期下降，则预测失效。",
  "U.S. easing dominates.": "若美国宽松因素占主导，则预测失效。",
  "Carry trades remain stable.": "若套利交易保持稳定，则预测失效。",
  "Yen and yield signals stay mixed.": "若日元和收益率信号持续混合，则预测可信度下降。",
  "Rate pressure dominates confidence.": "若利率压力压过信心改善，则预测失效。",
  "China growth confidence fails.": "若中国增长信心未改善，则预测失效。",
  "U.S. term premium rises.": "若美国期限溢价上升，则预测失效。",
  "Policy transmission disappoints.": "若政策传导效果不及预期，则预测失效。",
  "Implementation is softened.": "若关税执行力度被削弱，则预测失效。",
  "Inflation dominates growth risk.": "若通胀风险压过增长风险，则利率方向预测失效。",
};

function zhText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const text = String(value);
  return ZH_TEXT[text] || SOURCE_TITLES_ZH[text] || ANALYSIS_TEXT_ZH[text] || labels[text] || text;
}

function bilingual(value, label = "中文摘要") {
  const original = String(value ?? "");
  const translated = zhText(original);
  if (!original || original === "UNKNOWN") return `<p class="unknown-text">${esc(t(original || "UNKNOWN"))}</p>`;
  if (translated === original) return `<p><b>${esc(label)}：</b>${esc(original)}</p>`;
  return `<p><b>${esc(label)}：</b>${esc(translated)}</p><details class="original-text"><summary>英文原文</summary><p>${esc(original)}</p></details>`;
}

function t(value) {
  if (value === null || value === undefined || value === "") return "—";
  return labels[value] || String(value);
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function json(value) {
  return `<pre class="json-block">${esc(JSON.stringify(value ?? {}, null, 2))}</pre>`;
}

function statusClass(value) {
  const raw = String(value || "");
  if (raw.includes("REJECT")) return "rejected";
  if (raw.includes("PENDING") || raw.includes("REQUIRED")) return "pending";
  if (raw.includes("PARTIAL") || raw.includes("INITIAL")) return "partial";
  if (raw.includes("VERIFIED") || raw.includes("APPROVED") || raw.includes("FORMAL")) return "verified";
  return "partial";
}

function badge(value) {
  return `<span class="status ${statusClass(value)}">${esc(t(value))}</span>`;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  window.setTimeout(() => element.classList.remove("show"), 1800);
}

async function api(path, channel = "main") {
  state.controllers.get(channel)?.abort();
  const controller = new AbortController();
  state.controllers.set(channel, controller);
  const response = await fetch(path, { signal: controller.signal });
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  return response.json();
}

function option(value, text, selected = false) {
  return `<option value="${esc(value)}" ${selected ? "selected" : ""}>${esc(text)}</option>`;
}

function populateSelect(id, values, current = "") {
  const element = $(id);
  element.innerHTML = option("", "全部") + values.map((value) => option(value, t(value), value === current)).join("");
}

function eventName(event) {
  const raw = event.title_zh || event.event_title_zh || event.event_title || event.title || event.event_id;
  return zhText(raw);
}

function renderOverview() {
  const o = state.overview;
  const metrics = [
    ["宏观事件", o.event_count, "全部事件均连接市场与公司"],
    ["市场归因题", o.market_sample_count, "每个事件 4 条正式样本"],
    ["公司档案", o.company_dossier_count, "每个事件 3 家 A 股公司"],
    ["公司候选样本", o.company_sample_count, "归因题与预测题合计"],
  ];
  $("#summary-metrics").innerHTML = metrics.map(([name, value, note]) =>
    `<div class="metric"><small>${esc(name)}</small><strong>${esc(value)}</strong><small>${esc(note)}</small></div>`
  ).join("");
  $("#overview-status").innerHTML = `${badge(o.market_formal_ready ? "FORMAL" : "PENDING_EVIDENCE")} ${badge(o.company_release_tier)} <span class="muted">公司正式发布：${o.company_formal_ready ? "已就绪" : "尚未就绪"}</span>`;
  $("#formal-blockers").innerHTML = `<strong>公司候选版尚未达到正式版</strong><div class="blocker-list">${(o.company_formal_blockers || []).map((item) => `<span>${esc(zhText(item))}</span>`).join("")}</div>`;
}

function renderEventHeader() {
  const event = state.workspace?.event || {};
  const originalTitle = event.title || event.event_title || "";
  $("#event-title").textContent = eventName(event);
  $("#event-meta").innerHTML = `<span>${esc(event.event_id || "")} · 发生时间 ${esc(event.occurred_at || "—")} · 首次公开 ${esc(event.first_public_at || "—")}</span>${originalTitle && zhText(originalTitle) !== originalTitle ? `<br><span>英文原文：${esc(originalTitle)}</span>` : ""}<br><span>候选传导渠道：${esc((event.candidate_channels || []).map(zhText).join("、") || "未记录")} · 证据来源 ${esc((event.source_ids || []).length)} 条</span>`;
  $("#event-source-status").innerHTML = `${badge("FORMAL")}<span class="status partial">4 条市场题</span><span class="status pending">3 家候选公司</span>`;
}

function marketSampleName(row) {
  const targets = (row.target_series_ids || []).join(" / ");
  return `${targets || "跨资产"} · ${t(row.task_type)} · ${t(row.label)}`;
}

function renderMarketSelector() {
  const rows = state.workspace?.market_samples || [];
  $("#market-sample-select").innerHTML = rows.map((row) => option(row.record_id, marketSampleName(row), row.record_id === state.marketId)).join("");
}

function renderMarket() {
  if (!state.market) return;
  const row = state.market.sample;
  $("#market-sample-summary").innerHTML = [
    `<strong>${esc((row.target_series_ids || []).join(" / "))}</strong>`,
    badge(row.attribution?.label),
    badge(row.attribution?.confidence),
    `<span class="muted">预测截止 ${esc(row.forecast_as_of_at)}</span>`,
  ].join("");
  $("#market-step-nav").innerHTML = state.market.steps.map((step, index) =>
    `<button class="step-button ${index === state.stepIndex ? "active" : ""}" data-step-index="${index}" role="tab"><span>STEP ${index + 1}</span><b>${esc(t(step.step_id))}</b></button>`
  ).join("");
  $$(".step-button").forEach((button) => button.addEventListener("click", () => {
    state.stepIndex = Number(button.dataset.stepIndex);
    renderMarket();
  }));
  renderMarketStep(state.market.steps[state.stepIndex]);
  $("#market-audit-content").innerHTML = json(state.market.audit_only);
}

function renderSources(sources = []) {
  if (!sources.length) return `<p class="muted">当前节点没有已解析来源。</p>`;
  return `<div class="source-list">${sources.map((source, index) => {
    const original = source.title || source.excerpt || source.source_id;
    const summary = zhText(source.excerpt || source.title || "");
    return `<article class="source-card"><div class="source-card-head"><span>${esc(source.publisher || "未知发布机构")}</span>${badge(source.verification_status || "VERIFIED")}</div><h4>${esc(zhText(source.title || source.source_id))}</h4>${summary && summary !== zhText(source.title || "") ? `<p><b>中文摘要：</b>${esc(summary)}</p>` : ""}<details class="original-text"><summary>英文原文</summary><p>${esc(original)}</p></details><div class="source-actions"><button class="source-open" data-source-index="${index}" type="button">查看归档详情</button>${source.source_url ? `<a class="source-link" href="${esc(source.source_url)}" target="_blank" rel="noreferrer">打开原文链接 ↗</a>` : `<span class="muted">无公开 URL</span>`}</div></article>`;
  }
  ).join("")}</div>`;
}

function windowRows(windows = []) {
  const rows = [];
  windows.forEach((window) => Object.entries(window.windows || {}).forEach(([code, item]) => {
    const seriesId = window.series?.series_id || window.market_window_id;
    const seriesName = window.series?.series_name_zh || zhText(seriesId);
    rows.push(`<tr><td><strong>${esc(seriesName)}</strong><br><small>${esc(seriesId)}</small></td><td>${esc(code)}</td><td>${esc(item?.end_date)}</td><td>${item?.change === undefined ? "—" : esc(item.change)}</td><td>${item?.abnormal_score === undefined ? "—" : esc(item.abnormal_score)}</td></tr>`);
  }));
  return `<table class="window-table"><thead><tr><th>序列</th><th>窗口</th><th>日期</th><th>变化</th><th>异常分数</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function translatedList(items = [], emptyText = "暂无记录") {
  if (!items.length) return `<p class="muted">${esc(emptyText)}</p>`;
  return `<div class="analysis-list">${items.map((item) => `<div class="analysis-item">${bilingual(item)}</div>`).join("")}</div>`;
}

function originalRecord(value) {
  return `<details class="raw-record"><summary>查看完整原始记录</summary>${json(value)}</details>`;
}

function renderMarketStep(step) {
  const c = step.content || {};
  let body = "";
  if (step.step_id === "MACRO_REPORT") {
    body = `<div class="reading-lead"><span>第 1 步</span><div><h3>先确认事件与宏观研报事实</h3><p>以下材料用于建立事件事实和事件前基线，不单独证明最终归因。</p></div></div>${renderSources(c.sources)}<h3>研报摘要</h3><div class="analysis-list">${(c.evidence || []).map((item) => `<div class="analysis-item">${bilingual(item.summary)}<p class="muted">发布时间 ${esc(item.published_at)} · 证据 ID ${esc(item.evidence_id)}</p></div>`).join("")}</div>${originalRecord(c.evidence)}`;
  } else if (step.step_id === "DATA") {
    body = `<div class="reading-lead"><span>第 2 步</span><div><h3>观察截止日前可见的市场变化</h3><p>预测截止 ${esc(c.forecast_as_of_at)}；公开判断只使用 D1 与 D3，D20 实际结果隔离在审计区。</p></div></div>${windowRows(c.market_windows)}<div class="explain-note"><strong>如何阅读：</strong>变化方向用于判断资产是否符合传导预期；异常分数用于判断波动是否明显偏离事件前 60 个交易日基准。</div>${originalRecord(c.market_windows)}`;
  } else if (step.step_id === "PERIOD_DESCRIPTION") {
    body = `<div class="reading-lead"><span>第 3 步</span><div><h3>明确事件与观察期的先后顺序</h3><p>这里只描述时间和观察结果，尚不构成因果结论。</p></div></div><div class="period-card">${bilingual(c.period_description?.summary)}<div class="period-range"><span>开始 ${esc(c.period_description?.start_date)}</span><b>→</b><span>结束 ${esc(c.period_description?.end_date)}</span></div></div>${windowRows(c.market_windows)}`;
  } else if (step.step_id === "FACT_TRANSMISSION_CHAIN") {
    body = `<div class="reading-lead"><span>第 4 步</span><div><h3>从重大事件追踪到市场重新定价</h3><p>中文摘要说明传导原因；英文原文可展开核对。</p></div></div><div class="market-chain">${(c.nodes || []).map((node, index) => `<div class="market-chain-node"><span>${index + 1}</span><strong>${esc(t(node.node_type))}</strong>${bilingual(node.statement)}</div>`).join("")}</div><div class="mechanism-grid"><section><h3>候选传导渠道</h3><div class="tag-list">${(c.channels || []).map((item) => `<span>${esc(zhText(item))}</span>`).join("") || "未记录"}</div></section><section><h3>竞争解释与反证</h3>${translatedList(c.counterevidence, "当前没有竞争解释记录")}</section></div>${originalRecord({ edges: c.edges, channels: c.channels, counterevidence: c.counterevidence })}`;
  } else if (step.step_id === "MULTI_DATA_TREND_CONFIRMATION") {
    const supports = (c.items || []).filter((item) => item.alignment === "SUPPORTS").length;
    body = `<div class="reading-lead"><span>第 5 步</span><div><h3>用多重市场数据检验传导趋势</h3><p>${esc(c.series_count)} 个序列中有 ${supports} 个方向支持当前传导判断；一致性增强可信度，但不等于严格因果证明。</p></div></div><div class="trend-grid">${(c.items || []).map((item) => `<article><strong>${esc(zhText(item.series_id))}</strong><small>${esc(item.series_id)} · ${esc(item.window)}</small><div><span>预期 ${esc(t(item.expected_direction))}</span><b>→</b><span>实际 ${esc(t(item.observed_direction))}</span></div>${badge(item.alignment)}</article>`).join("")}</div>${originalRecord(c)}`;
  } else {
    const p = c.prediction || {};
    body = `<div class="prediction-hero"><div><span>第 6 步 · 事前短期预测</span><h3>${esc(zhText(p.target_series_id))} 在 ${esc(p.horizon)} 窗口预测为 <strong>${esc(t(p.direction))}</strong></h3><p>置信度：${esc(t(p.confidence))} · 预测截止：${esc(c.forecast_as_of_at)}</p></div><div class="prediction-direction ${String(p.direction || "").toLowerCase()}">${esc(t(p.direction))}</div></div><section class="invalidation-panel"><h3>什么情况下该预测失效</h3>${translatedList(p.invalidation_conditions, "未记录失效条件")}</section><div class="explain-note"><strong>防泄漏说明：</strong>这里展示的是截止日当时形成的预测；D20 实际方向、数值和验证结果只在事后审计区。</div>${originalRecord(p)}`;
  }
  $("#market-step-content").innerHTML = body;
  $$("#market-step-content .source-open").forEach((button) => button.addEventListener("click", () => {
    openDrawer((c.sources || [])[Number(button.dataset.sourceIndex)], "市场来源");
  }));
}

function filteredCompanies() {
  const rows = state.workspace?.companies || [];
  const query = $("#company-filter").value.trim().toLowerCase();
  const association = $("#association-filter").value;
  const direction = $("#direction-filter").value;
  const evidence = $("#evidence-filter").value;
  const review = $("#review-filter").value;
  return rows.filter((row) =>
    (!query || `${row.company_code} ${row.company_name}`.toLowerCase().includes(query)) &&
    (!association || row.association === association) &&
    (!direction || row.direction === direction) &&
    (!evidence || row.evidence_status === evidence) &&
    (!review || row.review_status === review)
  );
}

function renderCompanySelector() {
  const all = state.workspace?.companies || [];
  populateSelect("#association-filter", [...new Set(all.map((row) => row.association).filter(Boolean))], $("#association-filter").value);
  populateSelect("#direction-filter", [...new Set(all.map((row) => row.direction).filter(Boolean))], $("#direction-filter").value);
  populateSelect("#evidence-filter", [...new Set(all.map((row) => row.evidence_status).filter(Boolean))], $("#evidence-filter").value);
  populateSelect("#review-filter", [...new Set(all.map((row) => row.review_status).filter(Boolean))], $("#review-filter").value);
  const rows = filteredCompanies();
  $("#company-count").textContent = `${rows.length} 家`;
  $("#company-selector").innerHTML = rows.length ? rows.map((row) =>
    `<button class="company-button ${row.dossier_id === state.dossierId ? "active" : ""}" data-dossier-id="${esc(row.dossier_id)}"><strong>${esc(row.company_name)} · ${esc(row.company_code)}</strong><small>${esc(row.industry)} · ${t(row.association)} · ${t(row.direction)}</small></button>`
  ).join("") : `<div class="notice">当前筛选条件下没有公司。</div>`;
  $$(".company-button").forEach((button) => button.addEventListener("click", () => loadCompany(button.dataset.dossierId)));
}

function formatMetricValue(row) {
  if (row.value === "UNKNOWN" || row.value === null || row.value === undefined) return "未知";
  const value = typeof row.value === "number" ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(row.value) : row.value;
  return `${value} ${zhText(row.unit || row.currency || "")}`.trim();
}

function renderMetricFacts(rows = []) {
  return `<div class="metric-fact-grid">${rows.map((row) => `<article class="metric-fact"><div><span>${esc(zhText(row.metric_type || row.metric_name))}</span>${badge(row.status)}</div><strong>${esc(formatMetricValue(row))}</strong><p>${esc(row.period === "UNKNOWN" ? "期间未知" : row.period)}${row.derivation_type ? ` · ${esc(zhText(row.derivation_type))}` : ""}</p>${row.gap_reason ? `<div class="gap-inline">${esc(zhText(row.gap_reason))}</div>` : ""}${(row.evidence_refs || []).some((ref) => ref.source_url) ? `<div class="metric-links">${row.evidence_refs.filter((ref) => ref.source_url).map((ref, index) => `<a class="source-link" href="${esc(ref.source_url)}" target="_blank" rel="noreferrer">官方报告 ${index + 1} ↗</a>`).join("")}</div>` : ""}</article>`).join("")}</div>`;
}

function renderStockWindow(window) {
  if (!window || !Object.keys(window).length) return `<div class="gap-state"><strong>行情窗口未建立</strong><p>当前档案没有个股与沪深 300 行情记录。</p></div>`;
  const available = Object.entries(window.windows || {}).filter(([, value]) => value);
  const summary = window.status === "PENDING_EVIDENCE" ? `<div class="gap-state"><strong>行情仍待补证</strong>${bilingual(window.gap_reason)}<p>因此当前不能计算个股相对沪深 300 的异常收益，也不能把行情作为公司归因证据。</p></div>` : "";
  return `<div class="company-readable-summary">${summary}${available.length ? `<table class="window-table"><thead><tr><th>窗口</th><th>个股收益</th><th>沪深 300</th><th>异常收益</th></tr></thead><tbody>${available.map(([code, item]) => `<tr><td>${esc(code)}</td><td>${esc(item.stock_return ?? "—")}</td><td>${esc(item.benchmark_return ?? "—")}</td><td>${esc(item.abnormal_return ?? "—")}</td></tr>`).join("")}</tbody></table>` : `<p class="muted">D1、D3、D5、D20 当前均无可审计数值。</p>`}${originalRecord(window)}</div>`;
}

function renderAttributionOutput(sample = {}) {
  return `<div class="decision-panel"><span>事后归因候选</span><h4>${esc(zhText(sample.association || "PENDING_ASSESSMENT"))}</h4><div class="decision-tags">${badge(sample.direction || "UNCERTAIN")}${badge(sample.confidence || "LOW")}${badge(sample.label_status || "PENDING_EVIDENCE")}</div><p>当前方向：${esc(zhText(sample.direction || "UNCERTAIN"))}。该结论属于候选训练标签，不能作为正式投资结论。</p></div>`;
}

function renderForecastOutput(sample = {}) {
  const rows = sample.forecast_labels || [];
  return `<div class="forecast-panel"><span>事前预测候选 · 截止 ${esc(sample.forecast_as_of_at || "—")}</span><div class="forecast-labels">${rows.map((row) => `<div><small>${esc(zhText(row.label_type))}</small><strong>${esc(zhText(row.value))}</strong>${badge(row.status)}</div>`).join("") || `<p>暂无预测标签。</p>`}</div><p class="muted">无法判断表示截止日前证据不足，不使用后续财报补写事前判断。</p></div>`;
}

function renderCompanyReviewPanel(review = {}, gaps = []) {
  const status = review.review_status || review.initial_review?.status || "PENDING_EVIDENCE";
  const triggers = review.second_review_trigger_reasons || [];
  return `<div class="review-summary"><div class="review-summary-head"><div><span>档案审核结论</span><h4>${esc(zhText(status))}</h4></div>${badge(status)}</div><p>初审人：${esc(review.initial_reviewer_id || review.initial_review?.reviewer_id || "未记录")} · 初审决定：${esc(zhText(review.initial_review?.decision || review.initial_review?.status || "UNKNOWN"))}</p><h5>为什么需要复审</h5><div class="trigger-list">${triggers.map((item) => `<span>${esc(zhText(item))}</span>`).join("") || `<span>未记录复审触发原因</span>`}</div><h5>仍需补齐的证据</h5>${renderRecords(gaps, (row) => `${zhText(row.node_type)}：${zhText(row.gap_reason)}`)}${originalRecord(review)}</div>`;
}

function renderCompany() {
  if (!state.company) return;
  const d = state.company.dossier;
  $("#company-identity").innerHTML = `<div><h3>${esc(d.company_name)} · ${esc(d.company_code)}</h3><span class="muted">${esc(d.industry)} · 观察季度 ${esc(d.observation_quarter?.value)} · 次季 ${esc(d.next_validation_quarter?.value)}</span></div><div>${badge(d.evidence_status)} ${badge(d.review_status)} ${badge(d.confidence)}</div>`;
  $("#company-chain").innerHTML = state.company.nodes.map((node, index) =>
    `<button class="chain-node ${statusClass(node.status)}" data-node-index="${index}" type="button"><span class="node-index">节点 ${index + 1}</span><b>${esc(t(node.node_type))}</b><p>${esc(zhText(node.value))}</p>${zhText(node.value) !== String(node.value) ? `<small>可查看英文原文</small>` : ""}<span class="status ${statusClass(node.status)}">${esc(t(node.status))}</span></button>`
  ).join("");
  $$(".chain-node").forEach((button) => button.addEventListener("click", () => openNode(Number(button.dataset.nodeIndex))));
  $("#company-metrics").innerHTML = `<div class="company-readable-summary">${renderMetricFacts(state.company.metric_facts)}</div>`;
  $("#company-stock").innerHTML = renderStockWindow(state.company.stock_window);
  $("#company-outputs").innerHTML = `<div class="company-readable-summary">${renderAttributionOutput(state.company.attribution_sample)}${renderForecastOutput(state.company.forecast_sample)}<h4>档案引用</h4>${renderSources(state.company.sources)}</div>`;
  $("#company-review").innerHTML = renderCompanyReviewPanel(state.company.review, state.company.evidence_gaps);
  $("#company-audit-content").innerHTML = json(state.company.audit_only);
  $$("#company-outputs .source-open").forEach((button) => button.addEventListener("click", () => openDrawer(state.company.sources[Number(button.dataset.sourceIndex)], "公司来源")));
}

function renderRecords(rows = [], formatter) {
  if (!rows.length) return `<p class="muted">暂无记录。</p>`;
  return `<div class="record-list">${rows.map((row) => `<div class="record">${esc(formatter(row))}</div>`).join("")}</div>`;
}

function openNode(index) {
  const node = state.company.nodes[index];
  const content = {
    node_id: node.node_id,
    node_type: t(node.node_type),
    value_zh: zhText(node.value),
    original_value: node.value,
    status: t(node.status),
    gap_reason_zh: zhText(node.gap_reason),
    evidence_gaps: (node.evidence_gaps || []).map((gap) => ({
      node_type: t(gap.node_type),
      status: t(gap.status),
      gap_reason_zh: zhText(gap.gap_reason),
      original_gap_reason: gap.gap_reason,
    })),
    unresolved_evidence_refs: node.unresolved_evidence_refs,
  };
  openDrawer(content, t(node.node_type), node.sources || []);
}

function openDrawer(content, title = "节点证据", sources = []) {
  $("#drawer-title").textContent = title;
  const sourceList = sources.length ? sources : (content?.source_id ? [content] : []);
  const summary = content?.value_zh || zhText(content?.excerpt || content?.title || content?.value || "");
  $("#chain-node-detail").innerHTML = `<section class="drawer-summary"><span>中文摘要</span><p>${esc(summary)}</p>${content?.original_value && content.original_value !== summary ? `<details class="original-text"><summary>英文原文</summary><p>${esc(content.original_value)}</p></details>` : ""}${content?.gap_reason_zh && content.gap_reason_zh !== "—" ? `<div class="gap-inline"><b>证据缺口：</b>${esc(content.gap_reason_zh)}</div>` : ""}</section><h3>引用列表</h3>${sourceList.length ? sourceList.map((source) => `<article class="source-card"><div class="source-card-head"><span>${esc(source.publisher || source.source_id)}</span>${badge(source.verification_status || "VERIFIED")}</div><h4>${esc(zhText(source.title || source.source_id))}</h4>${bilingual(source.excerpt || source.title || "无摘录")}<p><b>定位：</b>${esc(JSON.stringify(source.source_locator || source.locator || {}))}</p><p><b>SHA-256：</b><code>${esc(source.content_sha256 || "UNKNOWN")}</code></p>${source.source_url ? `<a class="source-link" href="${esc(source.source_url)}" target="_blank" rel="noreferrer">打开原文链接 ↗</a>` : `<span class="muted">没有公开 URL</span>`}</article>`).join("") : `<p class="muted">没有已归档引用；请查看上方缺口原因。</p>`}${originalRecord(content)}`;
  $("#evidence-drawer").classList.add("open");
  $("#evidence-drawer").setAttribute("aria-hidden", "false");
  $("#drawer-scrim").hidden = false;
}

function closeDrawer() {
  $("#evidence-drawer").classList.remove("open");
  $("#evidence-drawer").setAttribute("aria-hidden", "true");
  $("#drawer-scrim").hidden = true;
}

function renderReviews() {
  const eventReviews = state.reviews.filter((row) => !state.eventId || row.event_id === state.eventId);
  $("#review-list").innerHTML = eventReviews.map((row) => {
    const reviewer = row.initial_reviewer_id || row.initial_review?.reviewer_id || "—";
    const status = row.review_status || row.adjudication?.status || row.initial_review?.status || "PENDING_EVIDENCE";
    const decision = row.final_label || row.adjudication?.label || row.initial_review?.label || row.initial_review?.decision || "PENDING_ASSESSMENT";
    const confidence = row.confidence || row.adjudication?.confidence || row.initial_review?.confidence;
    const dimensions = row.core_dimensions || row.adjudication?.core_dimensions || row.initial_review?.core_dimensions || {};
    const triggers = row.second_review_trigger_reasons || [];
    const comments = row.adjudication?.comments || row.second_review?.comments || row.initial_review?.comments || "";
    const domainName = row.domain === "MARKET" ? "市场归因审核" : "公司影响审核";
    const target = row.domain === "MARKET" ? reviewTargetName(row.review_id) : `${row.company_code || ""} 公司档案`;
    return `<article class="review-row review-summary"><div class="review-summary-head"><div><span>${esc(domainName)} · ${esc(row.event_id)}</span><h3>${esc(target)}</h3></div>${badge(status)}</div><div class="review-decision"><div><small>最终判断</small><strong>${esc(zhText(decision))}</strong></div><div><small>置信度</small><strong>${esc(zhText(confidence || "UNKNOWN"))}</strong></div><div><small>初审人</small><strong>${esc(reviewer)}</strong></div></div>${Object.keys(dimensions).length ? `<h4>四个核心归因维度</h4><div class="dimension-grid">${Object.entries(dimensions).map(([key, value]) => `<div><span>${esc(zhText(key))}</span><strong>${esc(zhText(value))}</strong></div>`).join("")}</div>` : ""}<h4>复审触发原因</h4><div class="trigger-list">${triggers.map((item) => `<span>${esc(zhText(item))}</span>`).join("") || `<span>没有记录复审触发原因</span>`}</div><div class="review-conclusion"><b>直观结论：</b>${esc(reviewConclusion(decision, confidence, dimensions, triggers))}</div>${comments ? `<details class="original-text"><summary>查看原始审核意见</summary><p>${esc(comments)}</p></details>` : ""}${originalRecord(row)}</article>`;
  }).join("") || `<div class="notice">当前事件没有审核记录。</div>`;
}

function reviewTargetName(reviewId = "") {
  const id = String(reviewId).toLowerCase();
  if (id.includes("cross-asset")) return "跨资产比较样本";
  if (id.includes("dcoilbrenteu")) return "布伦特原油样本";
  if (id.includes("dcoilwtico")) return "WTI 原油样本";
  if (id.includes("vixcls")) return "市场波动率样本";
  if (id.includes("sp500")) return "标普 500 样本";
  if (id.includes("dgs10")) return "美国 10 年期国债收益率样本";
  if (id.includes("dexchus")) return "美元兑人民币样本";
  return reviewId || "市场样本";
}

function reviewConclusion(decision, confidence, dimensions, triggers) {
  const parts = [`审核判断为“${zhText(decision)}”`, `置信度为“${zhText(confidence || "UNKNOWN")}”`];
  if (dimensions.temporal_alignment) parts.push(`时点吻合：${zhText(dimensions.temporal_alignment)}`);
  if (dimensions.abnormal_movement) parts.push(`异常程度：${zhText(dimensions.abnormal_movement)}`);
  if ((triggers || []).length) parts.push(`仍需关注 ${triggers.map(zhText).join("、")}`);
  return `${parts.join("；")}。`;
}

async function loadMarket(recordId) {
  state.marketId = recordId;
  state.stepIndex = 0;
  renderMarketSelector();
  try {
    state.market = await api(`/api/market-samples/${encodeURIComponent(recordId)}`, "market");
    renderMarket();
  } catch (error) {
    if (error.name !== "AbortError") toast(`市场样本加载失败：${error.message}`);
  }
}

async function loadCompany(dossierId) {
  state.dossierId = dossierId;
  renderCompanySelector();
  try {
    state.company = await api(`/api/company-chains/${encodeURIComponent(dossierId)}`, "company");
    renderCompany();
  } catch (error) {
    if (error.name !== "AbortError") toast(`公司档案加载失败：${error.message}`);
  }
}

async function loadEvent(eventId) {
  state.eventId = eventId;
  try {
    state.workspace = await api(`/api/events/${encodeURIComponent(eventId)}`, "event");
    state.marketId = state.workspace.market_samples[0]?.record_id || "";
    state.dossierId = state.workspace.companies[0]?.dossier_id || "";
    renderEventHeader();
    renderMarketSelector();
    renderCompanySelector();
    renderReviews();
    await Promise.all([
      state.marketId ? loadMarket(state.marketId) : Promise.resolve(),
      state.dossierId ? loadCompany(state.dossierId) : Promise.resolve(),
    ]);
  } catch (error) {
    if (error.name !== "AbortError") toast(`事件加载失败：${error.message}`);
  }
}

function bindEvents() {
  $$(".view-tab").forEach((button) => button.addEventListener("click", () => {
    $$(".view-tab").forEach((item) => item.classList.toggle("active", item === button));
    $$(".view").forEach((view) => view.classList.toggle("active", view.id === `${button.dataset.view}-view`));
  }));
  $("#event-filter").addEventListener("change", (event) => loadEvent(event.target.value));
  $("#market-sample-select").addEventListener("change", (event) => loadMarket(event.target.value));
  ["#company-filter", "#association-filter", "#direction-filter", "#evidence-filter", "#review-filter"].forEach((id) => {
    $(id).addEventListener(id === "#company-filter" ? "input" : "change", renderCompanySelector);
  });
  $("#reset-filters").addEventListener("click", () => {
    $("#company-filter").value = "";
    ["#association-filter", "#direction-filter", "#evidence-filter", "#review-filter"].forEach((id) => { $(id).value = ""; });
    renderCompanySelector();
  });
  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#drawer-scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeDrawer(); });
}

async function init() {
  bindEvents();
  try {
    [state.overview, state.events, state.reviews] = await Promise.all([
      api("/api/overview", "overview"),
      api("/api/events", "events"),
      api("/api/reviews", "reviews"),
    ]);
    renderOverview();
    $("#event-filter").innerHTML = state.events.map((event) => option(event.event_id, `${event.event_id} · ${eventName(event)}`)).join("");
    if (state.events.length) await loadEvent(state.events[0].event_id);
  } catch (error) {
    toast(`工作台初始化失败：${error.message}`);
    $("#overview-status").textContent = error.message;
  }
}

document.addEventListener("DOMContentLoaded", init);
