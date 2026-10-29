"""Attach public research Q&A to each event in the existing workbench."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import fingoose_company_impact_ui_v2 as _base
from fingoose_company_impact_io_v2 import read_jsonl


QA_STYLE = r"""
<style>
.section-jumps{position:sticky;top:58px;z-index:12;display:flex;gap:4px;overflow-x:auto;padding:9px 0;background:rgba(244,245,242,.97);border-bottom:1px solid var(--line)}
.section-jumps a{flex:0 0 auto;color:var(--muted);text-decoration:none;font-size:12px;font-weight:700;padding:6px 9px;border-left:2px solid transparent}
.section-jumps a:hover{color:var(--ink);border-left-color:var(--accent)}
.qa-section{scroll-margin-top:108px}.qa-head-meta{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.qa-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);background:var(--line);gap:1px;margin-bottom:16px}
.qa-tab{min-height:46px;border:0;background:var(--paper);color:var(--muted);font:inherit;font-weight:700;cursor:pointer;padding:9px 10px}
.qa-tab:hover{color:var(--ink)}.qa-tab.active{background:var(--ink);color:#fff;box-shadow:inset 0 -3px var(--gold)}
.qa-question{padding:16px 18px;border-left:4px solid var(--accent);background:var(--paper);margin-bottom:16px}
.qa-question b{display:block;font-size:15px}.qa-question p{margin:6px 0 0;color:#3f4a4d}
.qa-focus{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:start;padding:14px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.qa-focus p{margin:0;font-size:15px}.qa-status{white-space:nowrap;color:var(--muted);font-size:11px;text-align:right}
.qa-layer{padding:22px 0;border-bottom:1px solid var(--line)}.qa-layer:last-child{border-bottom:0}.qa-layer h3{margin:0 0 4px;font-size:16px}.qa-layer>p{margin:0 0 12px;color:var(--muted)}
.qa-evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.qa-evidence{min-width:0;padding:12px;border:1px solid var(--line);background:var(--paper)}
.qa-evidence b{display:block;font-size:12px}.qa-evidence p{margin:6px 0;color:#3f4a4d;font-size:12px}.qa-evidence small{display:block;color:var(--muted);overflow-wrap:anywhere}.qa-evidence a{display:inline-block;margin-top:7px}
.qa-mechanism{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}.qa-step{position:relative;min-width:0;padding:10px 8px;border-top:3px solid var(--teal);background:var(--paper);font-size:11px;overflow-wrap:anywhere}.qa-step b{display:block;color:var(--muted);font-size:10px}.qa-step p{margin:4px 0 0}.qa-step:not(:last-child):after{content:"›";position:absolute;right:-5px;top:32px;color:var(--accent);z-index:2}
.qa-horizons{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:10px}.qa-horizon{padding:9px;background:var(--soft);font-size:12px}.qa-horizon b{display:block;color:var(--muted);font-size:10px}
.qa-impact-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.qa-impact{min-width:0;padding:10px;border:1px solid var(--line);background:var(--paper)}.qa-impact b{display:block}.qa-impact small{color:var(--muted)}
.qa-market-table{width:100%;border-collapse:collapse;min-width:760px}.qa-market-table th,.qa-market-table td{padding:7px;border-bottom:1px solid var(--line);font-size:11px;text-align:right}.qa-market-table th:first-child,.qa-market-table td:first-child{text-align:left}
.qa-refusals{display:grid;gap:5px}.qa-refusal{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:8px 10px;background:var(--warn);border-left:3px solid var(--gold);font-size:11px}.qa-boundary{padding:11px 13px;background:#eef2ef;border-left:3px solid var(--teal);color:#405052}
.qa-jumps{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.qa-jump{border:1px solid var(--line);background:#fff;color:var(--ink);font:inherit;font-size:12px;font-weight:700;padding:8px 10px;cursor:pointer}.qa-jump:hover{border-color:var(--teal);color:var(--teal)}
@media(max-width:1100px){.qa-mechanism{grid-template-columns:repeat(4,minmax(0,1fr))}.qa-impact-list{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.section-jumps{top:52px;margin:0 -12px;padding:8px 12px}.qa-head-meta{justify-content:flex-start}.qa-tabs{grid-template-columns:repeat(2,minmax(0,1fr))}.qa-focus{grid-template-columns:1fr}.qa-status{text-align:left}.qa-evidence-grid,.qa-impact-list{grid-template-columns:1fr}.qa-mechanism{grid-template-columns:repeat(2,minmax(0,1fr))}.qa-horizons{grid-template-columns:1fr}.qa-refusal{grid-template-columns:1fr}.qa-question{padding:13px}}
</style>
"""


QA_OVERRIDE = r"""
<script>
const qaTaskLabels={MAIN_REASONING:'综合研判',EVIDENCE_AUDIT:'证据核查',MARKET_VALIDATION:'行情验证',INDUSTRY_COMPANY:'行业—公司'};
const qaLayerLabels={SOURCE_FACTS:'来源事实',RESEARCH_INFERENCE:'研究推断',CALCULATED_FACTS:'计算事实',REFUSAL_AND_BOUNDARIES:'拒答与边界'};
function qaPair(event){
  const rows=event.qa||[];
  return rows.find(row=>row.case.task_type===state.qaTaskType)||rows[0]||null;
}
function qaEvidenceHtml(rows){
  if(!rows.length)return '<div class="empty">截止日前没有满足原文、定位符与直达链接合同的证据。</div>';
  return '<div class="qa-evidence-grid">'+rows.slice(0,6).map(row=>'<article class="qa-evidence"><b>'+esc(row.publisher||row.evidence_id)+'</b><p>'+esc(row.original_quote)+'</p><small>'+esc(row.locator)+' · 首次公开 '+esc(row.first_public_at)+'</small><small>SHA-256 '+esc(row.snapshot_sha256||'待补')+'</small><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看官方原文</a></article>').join('')+'</div>';
}
function qaMechanismHtml(answer){
  const steps=answer.mechanism_chain||[];
  const horizons=answer.horizon_summary||{};
  return '<div class="qa-mechanism">'+steps.map(row=>'<div class="qa-step"><b>'+esc(row.step)+' · '+esc(row.node_type)+'</b><p>'+esc(row.statement_zh||'待人工复核')+'</p></div>').join('')+'</div><div class="qa-horizons">'+[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']].map(([key,label])=>'<div class="qa-horizon"><b>'+label+'</b>'+esc(horizons[key]||'UNKNOWN')+'</div>').join('')+'</div>';
}
function qaImpactsHtml(rows){
  return '<div class="qa-impact-list">'+rows.map(row=>'<div class="qa-impact"><b>'+esc(row.industry_name_zh)+' · '+esc(row.impact_tier)+'</b><small>'+esc((row.horizon_directions||{}).IMMEDIATE||'UNKNOWN')+' / '+esc((row.horizon_directions||{}).SHORT_TERM||'UNKNOWN')+' / '+esc((row.horizon_directions||{}).MEDIUM_TERM||'UNKNOWN')+'</small><p>'+esc(row.behavior_change_zh||row.observable_driver_zh||'机制待复核')+'</p></div>').join('')+'</div>';
}
function qaMarketHtml(rows){
  const keys=['T_MINUS_1','T0','D1','D3','D5','D20'];
  return '<div class="table-wrap"><table class="qa-market-table"><thead><tr><th>行业</th>'+keys.map(key=>'<th>'+esc(key.replace('T_MINUS_1','T-1'))+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr><td>'+esc(row.industry_name_zh)+'</td>'+keys.map(key=>{const point=(row.fixed_windows||{})[key];return '<td>'+(!point||point.market_relative_return==null?'—':pct(point.market_relative_return))+'</td>'}).join('')+'</tr>').join('')+'</tbody></table></div>';
}
function qaRefusalHtml(rows){
  if(!rows.length)return '<div class="qa-boundary">当前未登记强制拒答项，但结论仍保持候选状态并等待人工审核。</div>';
  return '<div class="qa-refusals">'+rows.slice(0,8).map(row=>'<div class="qa-refusal"><span>'+esc(row.scope_id)+'</span><b>'+esc(row.direction)+' · '+esc(row.decision)+' · '+esc(row.refusal_reason)+'</b></div>').join('')+'</div>';
}
function qaSection(event){
  if(state.qaEventId!==event.event_id){state.qaEventId=event.event_id;state.qaTaskType='MAIN_REASONING'}
  const pair=qaPair(event);
  if(!pair)return '<section class="section qa-section" id="qa"><div class="empty">研究问答候选包未加载。</div></section>';
  const question=pair.case,answer=pair.answer,layers=answer.answer_layers||{};
  const tabs=Object.keys(qaTaskLabels).map(key=>'<button class="qa-tab '+(key===answer.task_type?'active':'')+'" data-qa-task="'+key+'" role="tab" aria-selected="'+(key===answer.task_type)+'">'+qaTaskLabels[key]+'</button>').join('');
  const source=layers.SOURCE_FACTS||{},inference=layers.RESEARCH_INFERENCE||{},calculated=layers.CALCULATED_FACTS||{},boundary=layers.REFUSAL_AND_BOUNDARIES||{};
  return '<section class="section qa-section" id="qa"><div class="section-head"><div><h2>研究问答</h2><p>围绕当前宏观事件补足证据、机制、行情和公司边界</p></div><div class="qa-head-meta"><span class="chip warn">'+esc(status(answer.status))+'</span><span class="chip">'+esc(status(answer.review_status))+'</span><span class="chip">截止 '+esc(answer.prediction_cutoff_at)+'</span></div></div><div class="qa-tabs" role="tablist" aria-label="研究问答视角">'+tabs+'</div><div class="qa-question"><b>'+esc(question.task_label_zh)+'</b><p>'+esc(question.question_zh)+'</p></div><div class="qa-focus"><p>'+esc(answer.answer_focus_zh)+'</p><div class="qa-status">formal_ready=false<br>sha_gate=DEFERRED</div></div><article class="qa-layer"><h3>'+qaLayerLabels.SOURCE_FACTS+'</h3><p>'+esc(source.summary_zh)+'</p>'+qaEvidenceHtml(answer.evidence||[])+'</article><article class="qa-layer"><h3>'+qaLayerLabels.RESEARCH_INFERENCE+'</h3><p>'+esc(inference.summary_zh)+'</p>'+qaMechanismHtml(answer)+qaImpactsHtml(answer.industry_impacts||[])+'</article><article class="qa-layer"><h3>'+qaLayerLabels.CALCULATED_FACTS+'</h3><p>'+esc(calculated.summary_zh)+'</p>'+qaMarketHtml(answer.market_windows||[])+'</article><article class="qa-layer"><h3>'+qaLayerLabels.REFUSAL_AND_BOUNDARIES+'</h3><p>'+esc(boundary.summary_zh)+'</p>'+qaRefusalHtml(answer.refusals||[])+'<div class="qa-jumps"><button class="qa-jump" data-qa-jump="timeline">下钻时间线</button><button class="qa-jump" data-qa-jump="transmission">下钻传导链</button><button class="qa-jump" data-qa-jump="industries">下钻行业</button><button class="qa-jump" data-qa-jump="companies">下钻公司</button></div></article></section>';
}
function bindQa(){
  document.querySelectorAll('[data-qa-task]').forEach(button=>button.onclick=()=>{state.qaTaskType=button.dataset.qaTask;renderMain();document.getElementById('qa').scrollIntoView({block:'start'})});
  document.querySelectorAll('[data-qa-jump]').forEach(button=>button.onclick=()=>{const target=document.getElementById(button.dataset.qaJump);if(target)target.scrollIntoView({block:'start'})});
}
renderMain=function(){
  const event=currentEvent();if(!state.qaTaskType)state.qaTaskType='MAIN_REASONING';if(!state.companyId&&event.companies.length)state.companyId=event.companies[0].company_id;
  document.getElementById('main').innerHTML='<section class="hero" id="overview"><div><span class="eyebrow">'+event.event_id.toUpperCase()+' · 高质量候选链</span><h1>'+esc(event.title)+'</h1><p>宏观事件为一级对象；问答用于补足事件证据、机制、行情与公司边界。</p></div><div class="hero-status"><b>正式发布：未就绪</b><span>AI 方向与公司公告均需人工复核</span></div></section><div class="metrics"><div class="metric"><b>'+event.summary.timeline_count+'</b><span>时间线节点</span></div><div class="metric"><b>'+event.summary.industry_mapping_count+'</b><span>行业影响</span></div><div class="metric"><b>'+event.summary.company_count+'</b><span>公司评估</span></div><div class="metric"><b>'+((event.qa||[]).length)+'</b><span>研究问题</span></div></div><nav class="section-jumps" aria-label="事件内容分布"><a href="#overview">事件概览</a><a href="#qa">研究问答</a><a href="#timeline">事件时间线</a><a href="#transmission">动态传导链</a><a href="#industries">行业影响</a><a href="#companies">公司影响</a></nav><div class="notice">本页为候选研究数据。证据存在不等于因果已确认；行情只用于验证，不用于事后选择方向。</div>'+qaSection(event)+'<section class="section" id="timeline"><div class="section-head"><h2>事件时间线</h2><p>点击节点联动其锚定的传导边</p></div><div class="timeline">'+renderTimeline(event)+'</div></section><section class="section" id="transmission"><div class="section-head"><h2>动态传导链</h2><p>即时、短期与中期方向均保持独立审核状态</p></div><div class="transmission-toolbar"><div class="transmission-tabs" role="tablist" aria-label="传导链视图"><button class="transmission-tab '+(state.transmissionMode==='operating'?'active':'')+'" data-transmission-mode="operating" role="tab">经营影响链</button><button class="transmission-tab '+(state.transmissionMode==='macro'?'active':'')+'" data-transmission-mode="macro" role="tab">宏观市场链</button><button class="transmission-tab '+(state.transmissionMode==='industry'?'active':'')+'" data-transmission-mode="industry" role="tab">行业板块链</button></div><button class="plain-button" id="show-all-paths">显示全部路径</button></div><div class="path-list">'+renderTransmission(event)+'</div></section><section class="section" id="industries"><div class="section-head"><h2>行业影响</h2><p>直接影响、二阶传导与条件性影响完整保留</p></div><div class="industry-strip">'+renderIndustries(event)+'</div></section><section class="section" id="companies"><div class="section-head"><h2>公司影响</h2><p>每个事件固定三家公司，禁止事后按股价挑选</p></div><div class="company-grid">'+renderCompanies(event)+'</div>'+companyDetail(event)+'</section><footer class="footer">数据版本 '+esc(DATA.dataset_version)+' · formal_ready=false · SHA 门禁 DEFERRED · 页面不包含隐藏评测标签</footer>';
  bind(event);bindQa();
};
renderMain();
</script>
"""


def _load_public_qa(qa_root: Path) -> dict[str, list[dict[str, Any]]]:
    cases = {
        str(row["case_id"]): row for row in read_jsonl(qa_root / "qa_cases.jsonl")
    }
    answers = {
        str(row["case_id"]): row
        for row in read_jsonl(qa_root / "qa_answer_candidates.jsonl")
    }
    if set(cases) != set(answers):
        raise ValueError("QA_PUBLIC_JOIN_MISMATCH")
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case_id in sorted(cases):
        case = cases[case_id]
        by_event[str(case["event_id"])].append(
            {"case": case, "answer": answers[case_id]}
        )
    return by_event


def build_ui_bundle(
    root: Path,
    *,
    qa_root: Path,
    candidate_root: Path | None = None,
    industry_root: Path | None = None,
    industry_overlay_root: Path | None = None,
) -> dict[str, Any]:
    bundle = _base.build_ui_bundle(
        root,
        candidate_root=candidate_root,
        industry_root=industry_root,
        industry_overlay_root=industry_overlay_root,
    )
    qa_by_event = _load_public_qa(qa_root.resolve())
    for event in bundle["events"]:
        event["qa"] = qa_by_event.get(str(event["event_id"]), [])
    bundle["summary"]["qa_case_count"] = sum(
        len(event["qa"]) for event in bundle["events"]
    )
    bundle["summary"]["qa_integration"] = "EVENT_LINKED_PUBLIC_ONLY"
    return bundle


def render_workbench(bundle: Mapping[str, Any]) -> str:
    html = _base.render_workbench(bundle)
    order = (
        '<script type="application/json" id="research-section-order">'
        '["事件概览","研究问答","事件时间线","动态传导链","行业影响","公司影响"]'
        "</script>"
    )
    html = html.replace("</head>", order + QA_STYLE + "</head>")
    return html.replace("</body>", QA_OVERRIDE + "</body>")


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
    (output_root / "index.html").write_text(
        render_workbench(bundle), encoding="utf-8"
    )
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
