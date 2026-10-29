"""Render task-specific Q&A answers inside the macro-event workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_001 import build_ui_bundle
from fingoose_company_impact_qa_ui_v2_impl_004 import render_workbench as _render_v4


TASK_ANSWER_STYLE = r"""
<style>
.qa-direct{border-left:4px solid var(--gold);padding:12px 14px;background:#f6f8f7;line-height:1.7;font-weight:700}.qa-task-block{padding:16px 0;border-top:1px solid var(--line)}.qa-task-block:first-child{border-top:0}.qa-task-block>h3{margin:0 0 5px;font-size:15px}.qa-task-block>p{margin:0 0 12px;color:#465356;line-height:1.65}.qa-classification{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--line);border-left:1px solid var(--line)}.qa-classification>div{padding:11px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.qa-classification b{display:block;font-size:18px}.qa-classification span{font-size:10px;color:var(--muted)}
.qa-stage-reasoning{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0}.qa-stage-reason{padding:13px;background:#f4f7f6;border-top:3px solid var(--teal)}.qa-stage-reason:nth-child(2){border-top-color:var(--gold)}.qa-stage-reason:nth-child(3){border-top-color:#59696c}.qa-stage-reason small{display:block;color:var(--muted);margin:4px 0 7px}.qa-stage-reason p{margin:0;line-height:1.65;font-size:12px}.qa-focus-list{margin:7px 0 0;padding-left:17px;font-size:11px;color:#465356}
.qa-audit-list{display:grid;gap:7px}.qa-audit-row{display:grid;grid-template-columns:88px 1fr;gap:10px;padding:10px 0;border-bottom:1px dashed var(--line)}.qa-audit-row b{font-size:10px;color:var(--teal)}.qa-audit-row p{margin:0;font-size:12px;line-height:1.6}.qa-market-results{display:grid;gap:8px}.qa-market-result{border-top:1px solid var(--line);padding:11px 0}.qa-market-result summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:12px;font-weight:800}.qa-market-result summary::-webkit-details-marker{display:none}.qa-verdict{font-size:10px;padding:3px 7px;border:1px solid var(--line)}.qa-verdict.supports{color:#176b4b;border-color:#8fbda9}.qa-verdict.weakens{color:#a13c30;border-color:#d4a098}.qa-verdict.indistinguishable{color:#86651d;border-color:#cdbb8d}.qa-verdict.data-missing{color:var(--muted)}.qa-verdict-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin:10px 0}.qa-verdict-item{padding:9px;background:var(--soft);font-size:11px;line-height:1.55}.qa-verdict-item b{display:block;margin-bottom:3px}.qa-window-detail th,.qa-window-detail td{font-size:10px;padding:7px 6px;white-space:nowrap}
.qa-company-results{display:grid;gap:12px}.qa-company-answer{border:1px solid var(--line);padding:14px}.qa-company-answer-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding-bottom:9px;border-bottom:1px solid var(--line)}.qa-company-answer-head h4{margin:0;font-size:15px}.qa-company-answer-head small{display:block;color:var(--muted);margin-top:3px}.qa-company-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 16px;margin-top:11px}.qa-company-field h5{margin:0 0 5px;font-size:10px;color:var(--muted)}.qa-company-field p{margin:0;font-size:12px;line-height:1.6}.qa-direction-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.qa-direction-strip span{padding:7px;background:var(--soft);font-size:10px}.qa-disclosure{margin-top:7px}.qa-disclosure summary{cursor:pointer;font-size:11px;font-weight:700;color:var(--teal)}.qa-disclosure blockquote{margin:7px 0;padding-left:9px;border-left:2px solid var(--gold);font-size:10px;line-height:1.55;color:#465356}.qa-compact-list{margin:0;padding-left:16px;font-size:11px;line-height:1.6}.qa-company-wide{grid-column:1/-1}
@media(max-width:900px){.qa-classification{grid-template-columns:repeat(2,minmax(0,1fr))}.qa-stage-reasoning,.qa-verdict-grid{grid-template-columns:1fr}.qa-company-grid{grid-template-columns:1fr}.qa-company-wide{grid-column:auto}.qa-market-result summary{align-items:flex-start}}
</style>
"""


TASK_ANSWER_OVERRIDE = r"""
<script>
function qaVerdictClass(value){return String(value||'').toLowerCase().replaceAll('_','-')}
function qaHorizonReasoningHtml(answer){
  const rows=answer.horizon_reasoning_zh||{};
  const stages=[['IMMEDIATE','即时','首轮预期与交易反应'],['SHORT_TERM','短期','经营兑现与反馈'],['MEDIUM_TERM','中期','持续性与结构变化']];
  return '<div class="qa-stage-reasoning">'+stages.map(function(item){const row=rows[item[0]]||{},focus=row.observation_focus_zh||[];return '<section class="qa-stage-reason"><b>'+item[1]+' · '+esc(row.label_zh||item[2])+'</b><small>观察窗口 '+esc((row.window_keys||[]).join(' + '))+'</small><p>'+esc(row.reasoning_zh||'该阶段推理待补充')+'</p><ul class="qa-focus-list">'+focus.map(function(value){return '<li>'+esc(value)+'</li>'}).join('')+'</ul></section>'}).join('')+'</div>';
}
function qaMechanismStepsHtml(answer){
  return '<div class="qa-mechanism">'+(answer.mechanism_chain||[]).map(function(row){return '<div class="qa-step"><b>'+esc(row.step)+' · '+esc(row.node_type_zh||nodeTypeLabelZh[row.node_type]||'研究节点')+'</b><p>'+esc(row.statement_zh||'待人工复核')+'</p></div>'}).join('')+'</div>';
}
function qaCommonJumps(){return '<div class="qa-jumps"><button class="qa-jump" data-qa-jump="timeline">下钻时间线</button><button class="qa-jump" data-qa-jump="transmission">下钻传导链</button><button class="qa-jump" data-qa-jump="industries">下钻行业</button><button class="qa-jump" data-qa-jump="companies">下钻公司</button></div>'}
function qaMainReasoningAnswer(answer){
  const layers=answer.answer_layers||{},source=layers.SOURCE_FACTS||{},inference=layers.RESEARCH_INFERENCE||{},calculated=layers.CALCULATED_FACTS||{},boundary=layers.REFUSAL_AND_BOUNDARIES||{};
  return '<article class="qa-task-block"><h3>来源事实</h3><p>'+esc(source.summary_zh||'')+'</p>'+qaEvidenceHtml(answer.evidence||[])+'</article><article class="qa-task-block"><h3>研究推断</h3><p>三个阶段分别回答首轮反应、经营兑现和结构持续性，不跨阶段复用同一结论。</p>'+qaHorizonReasoningHtml(answer)+qaMechanismStepsHtml(answer)+qaImpactsHtml(answer.industry_impacts||[])+'</article><article class="qa-task-block"><h3>计算事实</h3><p>'+esc(calculated.summary_zh||'')+'</p>'+qaMarketHtml(answer.market_windows||[])+'</article><article class="qa-task-block"><h3>拒答与边界</h3><p>'+esc(boundary.summary_zh||'')+'</p>'+qaRefusalHtml(answer.refusals||[])+'</article>';
}
function qaEvidenceAuditAnswer(answer){
  const task=answer.task_answer||{},facts=task.official_facts||[],inferences=task.research_inferences||[],calculated=task.calculated_facts||[],boundaries=task.refusal_boundaries||[];
  return '<div class="qa-classification"><div><b>'+facts.length+'</b><span>官方事实</span></div><div><b>'+inferences.length+'</b><span>研究推断</span></div><div><b>'+calculated.length+'</b><span>计算事实</span></div><div><b>'+boundaries.length+'</b><span>拒答边界</span></div></div><article class="qa-task-block"><h3>官方事实</h3><p>仅列截止日前、可定位并可直达原文的来源；中文释义与审计原文并列。</p>'+qaEvidenceHtml(facts)+'</article><article class="qa-task-block"><h3>研究推断</h3><p>以下内容来自事实之后的机制连接，不冒充官方结论。</p><div class="qa-audit-list">'+inferences.map(function(row){return '<div class="qa-audit-row"><b>'+esc(row.type_zh||'研究推断')+'</b><p>'+esc(row.inference_zh||'待复核')+'</p></div>'}).join('')+'</div></article><article class="qa-task-block"><h3>计算事实</h3><p>共 '+calculated.length+' 组行业窗口，统一使用“行业收益 - 沪深300收益”的相对收益公式。</p>'+qaMarketHtml(answer.market_windows||[])+'</article><article class="qa-task-block"><h3>拒答边界</h3>'+qaRefusalHtml(boundaries)+'</article>';
}
function qaWindowCell(value){return value==null?'—':pct(value)}
function qaIndustryWindowsTable(row){
  const keys=['T_MINUS_1','T0','D1','D3','D5','D20'],windows=row.windows||{};
  return '<div class="table-wrap"><table class="qa-window-detail"><thead><tr><th>窗口</th><th>实际日期</th><th>行业收益</th><th>沪深300收益</th><th>相对收益</th></tr></thead><tbody>'+keys.map(function(key){const point=windows[key]||{};return '<tr><td>'+esc(key.replace('T_MINUS_1','T-1'))+'</td><td>'+esc(point.actual_date||'—')+'</td><td>'+qaWindowCell(point.industry_return)+'</td><td>'+qaWindowCell(point.market_return)+'</td><td>'+qaWindowCell(point.market_relative_return)+'</td></tr>'}).join('')+'</tbody></table></div>';
}
function qaMarketValidationAnswer(answer){
  const task=answer.task_answer||{},rows=task.industry_results||[];
  return '<article class="qa-task-block"><h3>验证口径</h3><p>'+esc(task.method_zh||'行情验证口径待补充')+'</p></article><article class="qa-task-block"><h3>行业结果与阶段判定</h3><p>展开行业查看六个固定窗口；“支持/削弱”只表示与预设机制方向是否一致，不表示因果成立。</p><div class="qa-market-results">'+rows.map(function(row){const verdicts=row.horizon_verdicts||{};return '<details class="qa-market-result"><summary><span>'+esc(row.industry_name_zh||row.event_industry_mapping_id)+'</span><span class="qa-verdict '+qaVerdictClass(row.overall_verdict)+'">总体 '+esc(row.overall_verdict_zh||row.overall_verdict)+'</span></summary><div class="qa-verdict-grid">'+[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']].map(function(item){const verdict=verdicts[item[0]]||{};return '<div class="qa-verdict-item"><b>'+item[1]+' · '+esc(verdict.verdict_zh||'待判定')+'</b>'+esc(verdict.basis_zh||'判定依据待补充')+'</div>'}).join('')+'</div>'+qaIndustryWindowsTable(row)+'</details>'}).join('')+'</div></article>';
}
function qaTextList(rows,empty){return rows&&rows.length?'<ul class="qa-compact-list">'+rows.map(function(row){return '<li>'+esc(row)+'</li>'}).join('')+'</ul>':'<p>'+esc(empty)+'</p>'}
function qaCompanyEvidenceHtml(rows){return (rows||[]).map(function(row){return '<details class="qa-disclosure"><summary>'+esc(row.document_title||row.claim_type)+' · '+esc(row.published_at)+'</summary><blockquote>'+esc(row.original_quote)+'</blockquote><small>'+esc(row.locator_zh||'定位待核验')+'</small><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看公司原始披露</a></details>'}).join('')}
function qaCounterevidenceHtml(rows,searchText){if(!rows||!rows.length)return '<p>'+esc(searchText||'未形成可展示反证，维持待核验。')+'</p>';return '<div>'+rows.slice(0,4).map(function(row){return '<details class="qa-disclosure"><summary>'+esc(row.document_title||row.claim_zh||'限制性证据')+'</summary><blockquote>'+esc(row.original_quote||row.claim_zh||'')+'</blockquote>'+(row.source_url?'<a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看原始披露</a>':'')+'</details>'}).join('')+'<p>'+esc(searchText||'')+'</p></div>'}
function qaConfounderHtml(rows){if(!rows||!rows.length)return '<p>已执行独立事项检索，当前未登记重大混杂。</p>';return '<ul class="qa-compact-list">'+rows.map(function(row){return '<li><b>'+esc(row.title_zh)+'</b>：'+esc(row.mechanism_zh||'独立公司因素')+'（'+esc((row.affected_windows||[]).join('、'))+'）</li>'}).join('')+'</ul>'}
function qaIndustryCompanyAnswer(answer){
  const task=answer.task_answer||{},rows=task.company_results||[];
  return '<article class="qa-task-block"><h3>公司逐一回答</h3><p>行业方向只用于定位暴露，公司结论必须由事件前披露、公司机制与独立混杂共同约束。</p><div class="qa-company-results">'+rows.map(function(row){const dirs=row.directions_zh||{};return '<article class="qa-company-answer"><div class="qa-company-answer-head"><div><h4>'+esc(row.company_name)+'</h4><small>'+esc(row.company_code)+' · '+esc(row.industry_name_zh)+'</small></div><span class="chip">'+esc(row.trading_status_zh)+'</span></div><div class="qa-company-grid"><section class="qa-company-field qa-company-wide"><h5>事件前业务披露</h5>'+qaCompanyEvidenceHtml(row.pre_event_disclosures||[])+'</section><section class="qa-company-field qa-company-wide"><h5>公司传导机制</h5><p>'+esc(row.mechanism_zh)+'</p></section><section class="qa-company-field"><h5>即时 / 短期 / 中期方向</h5><div class="qa-direction-strip"><span>即时 '+esc(dirs.IMMEDIATE||'未知')+'</span><span>短期 '+esc(dirs.SHORT_TERM||'未知')+'</span><span>中期 '+esc(dirs.MEDIUM_TERM||'未知')+'</span></div></section><section class="qa-company-field"><h5>停复牌核验</h5><p>'+esc(row.suspension_status_zh)+'</p></section><section class="qa-company-field"><h5>成立条件</h5>'+qaTextList(row.conditions_zh,'尚未登记成立条件')+'</section><section class="qa-company-field"><h5>限制与失效条件</h5>'+qaTextList(row.invalidation_conditions_zh,'尚未登记失效条件')+'</section><section class="qa-company-field"><h5>反证</h5>'+qaCounterevidenceHtml(row.counterevidence||[],row.counterevidence_search_zh)+'</section><section class="qa-company-field"><h5>独立混杂</h5>'+qaConfounderHtml(row.confounders||[])+'</section><section class="qa-company-field qa-company-wide"><h5>当前判断</h5><p>'+esc(row.decision_zh)+'</p></section></div></article>'}).join('')+'</div></article>';
}
function qaTaskAnswerBody(answer){
  if(answer.task_type==='EVIDENCE_AUDIT')return qaEvidenceAuditAnswer(answer);
  if(answer.task_type==='MARKET_VALIDATION')return qaMarketValidationAnswer(answer);
  if(answer.task_type==='INDUSTRY_COMPANY')return qaIndustryCompanyAnswer(answer);
  return qaMainReasoningAnswer(answer);
}
function qaSection(event){
  if(state.qaEventId!==event.event_id){state.qaEventId=event.event_id;state.qaTaskType='MAIN_REASONING'}
  const pair=qaPair(event);
  if(!pair)return '<section class="section qa-section" id="qa"><div class="empty">研究问答候选包未加载。</div></section>';
  const question=pair.case,answer=pair.answer;
  const tabs=Object.keys(qaTaskLabels).map(function(key){return '<button class="qa-tab '+(key===answer.task_type?'active':'')+'" data-qa-task="'+key+'" role="tab" aria-selected="'+(key===answer.task_type)+'">'+qaTaskLabels[key]+'</button>'}).join('');
  return '<section class="section qa-section" id="qa"><div class="section-head"><div><h2>研究问答</h2><p>围绕当前宏观事件补足证据、机制、行情和公司边界</p></div><div class="qa-head-meta"><span class="chip warn">'+esc(status(answer.status))+'</span><span class="chip">'+esc(status(answer.review_status))+'</span><span class="chip">截止 '+esc(answer.prediction_cutoff_at)+'</span></div></div><div class="qa-tabs" role="tablist" aria-label="研究问答视角">'+tabs+'</div><div class="qa-question"><b>'+esc(question.task_label_zh)+'</b><p>'+esc(question.question_zh)+'</p></div><div class="qa-direct">'+esc(answer.answer_focus_zh)+'</div>'+qaTaskAnswerBody(answer)+qaCommonJumps()+'</section>';
}
renderMain();
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    html = _render_v4(bundle)
    html = html.replace("</head>", TASK_ANSWER_STYLE + "</head>")
    return html.replace("</body>", TASK_ANSWER_OVERRIDE + "</body>")


def write_ui(
    root: Path,
    output_root: Path,
    *,
    qa_root: Path,
    candidate_root: Path | None = None,
    industry_root: Path | None = None,
    industry_overlay_root: Path | None = None,
) -> dict[str, Any]:
    bundle = build_ui_bundle(
        root,
        qa_root=qa_root,
        candidate_root=candidate_root,
        industry_root=industry_root,
        industry_overlay_root=industry_overlay_root,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "ui_data_bundle.js").write_text(
        "window.FINGOOSE_COMPANY_IMPACT_V2="
        + json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (output_root / "index.html").write_text(render_workbench(bundle), encoding="utf-8")
    return bundle["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--industry", type=Path, required=True)
    parser.add_argument("--industry-overlay", type=Path)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    def resolve(path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else root / path

    summary = write_ui(
        root,
        resolve(args.output),
        qa_root=resolve(args.qa),
        candidate_root=resolve(args.candidate),
        industry_root=resolve(args.industry),
        industry_overlay_root=resolve(args.industry_overlay),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["build_ui_bundle", "main", "render_workbench", "write_ui"]
