"""Render Chinese evidence facts and concrete three-horizon research detail."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_001 import build_ui_bundle
from fingoose_company_impact_qa_ui_v2_impl_003 import render_workbench as _render_v3


CHINESE_DETAIL_STYLE = r"""
<style>
.qa-evidence{padding:14px}.qa-evidence-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.qa-evidence-head b{font-size:14px}.qa-evidence h4{font-size:11px;color:var(--muted);margin:12px 0 4px}.qa-evidence .fact-zh{font-size:13px;color:var(--ink);line-height:1.65}.qa-source-original{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}.qa-source-original summary{cursor:pointer;color:var(--teal);font-weight:700;font-size:11px}.qa-source-original blockquote{margin:9px 0;padding-left:10px;border-left:2px solid var(--gold);color:#465356;font-size:11px}.qa-source-original small{margin-top:5px}
.qa-mechanism{margin-top:12px}.qa-horizons{gap:8px}.qa-horizon{border-left:3px solid var(--line);padding:11px}.qa-horizon strong{display:block;margin-top:4px;line-height:1.55}.qa-horizon.positive{border-left-color:#1c7c54}.qa-horizon.negative{border-left-color:#b24a3b}.qa-horizon.mixed{border-left-color:#b08735}.qa-horizon.unknown{border-left-color:#7a8587}
.qa-impact-list{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.qa-impact{padding:14px}.qa-impact-head{display:flex;justify-content:space-between;gap:10px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:8px}.qa-impact-head b{font-size:14px}.qa-tier{font-size:10px;font-weight:800;color:var(--teal)}.qa-impact-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px;margin:10px 0}.qa-impact-fact{font-size:11px;color:#465356}.qa-impact-fact b{display:block;color:var(--muted);font-size:9px;margin-bottom:2px}.qa-impact-stages{display:grid;gap:6px}.qa-impact-stage{padding:8px 9px;background:var(--soft);border-left:3px solid var(--line)}.qa-impact-stage.positive{border-left-color:#1c7c54}.qa-impact-stage.negative{border-left-color:#b24a3b}.qa-impact-stage.mixed{border-left-color:#b08735}.qa-impact-stage.unknown{border-left-color:#7a8587}.qa-impact-stage b{font-size:11px}.qa-impact-stage p{font-size:11px;line-height:1.6;margin:4px 0 0;color:#3f4a4d}.qa-boundaries{margin-top:9px;padding-top:8px;border-top:1px dashed var(--line);font-size:10px;color:var(--muted)}.qa-boundaries span{display:block;margin-top:3px}
@media(max-width:900px){.qa-impact-list{grid-template-columns:1fr}.qa-impact-facts{grid-template-columns:1fr}}
</style>
"""


CHINESE_DETAIL_OVERRIDE = r"""
<script>
const directionLabelZh={POSITIVE:'正向',NEGATIVE:'负向',MIXED:'分化',UNKNOWN:'未知'};
const tierLabelZh={CORE_DIRECT:'直接影响',SECOND_ORDER:'二阶传导',CONDITIONAL:'条件性影响'};
const nodeTypeLabelZh={EVENT_FACT:'事件事实',BEHAVIOR_OR_POLICY_CHANGE:'行为或政策变化',OBSERVABLE_DRIVER:'可观察驱动',INDUSTRY_OPERATING_VARIABLE:'行业经营变量',INDUSTRY_REVENUE_OR_COST_VARIABLE:'行业收入或成本变量',DIRECTION_ASSESSMENT:'方向研判',PRICE_CONFOUNDER_AND_COUNTEREVIDENCE:'行情、混杂与反证'};
const refusalReasonZh={ANCHOR_POST_CUTOFF:'事件锚点晚于截止日',INDUSTRY_CLOSURE_OPEN:'行业证据闭环尚未关闭',COMPANY_CLOSURE_OPEN:'公司证据闭环尚未关闭',TRADING_STATUS_UNVERIFIED:'停复牌状态尚未核验',CONFOUNDER_MATERIAL:'存在重大混杂因素',CONFOUNDER_DOMINANT:'混杂因素可能占主导',CONFOUNDER_UNRESOLVED:'混杂因素尚未解决'};
function qaDirectionClass(value){return ({POSITIVE:'positive',NEGATIVE:'negative',MIXED:'mixed',UNKNOWN:'unknown'})[value]||'unknown'}
function qaEvidenceHtml(rows){
  if(!rows.length)return '<div class="empty">截止日前没有满足原文、定位符与直达链接合同的证据。</div>';
  return '<div class="qa-evidence-grid">'+rows.slice(0,8).map(function(row){return '<article class="qa-evidence"><div class="qa-evidence-head"><b>'+esc(row.publisher_zh||row.publisher||row.evidence_id)+'</b><span class="chip">'+esc(row.source_tier||'官方来源')+'</span></div><h4>中文事实摘录</h4><p class="fact-zh">'+esc(row.fact_zh||row.original_quote)+'</p><small>'+esc(row.locator_zh||'官方页面对应引文段落')+' · 首次公开 '+esc(row.first_public_at)+'</small><details class="qa-source-original"><summary>审计原文</summary><blockquote>'+esc(row.original_quote)+'</blockquote><small>原始发布机构：'+esc(row.publisher||'待核验')+'</small><small>原始定位：'+esc(row.locator||'待核验')+'</small><small>SHA-256 '+esc(row.snapshot_sha256||'待补')+'</small></details><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看官方原文</a></article>'}).join('')+'</div>';
}
function qaMechanismHtml(answer){
  const steps=answer.mechanism_chain||[];
  const summaries=answer.horizon_summary_zh||{};
  const raw=answer.horizon_summary||{};
  const stages=[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']];
  return '<div class="qa-mechanism">'+steps.map(function(row){return '<div class="qa-step"><b>'+esc(row.step)+' · '+esc(row.node_type_zh||nodeTypeLabelZh[row.node_type]||'研究节点')+'</b><p>'+esc(row.statement_zh||'待人工复核')+'</p></div>'}).join('')+'</div><div class="qa-horizons">'+stages.map(function(item){const key=item[0],label=item[1],direction=raw[key]||'UNKNOWN';return '<div class="qa-horizon '+qaDirectionClass(direction)+'"><b>'+label+' · '+esc(directionLabelZh[direction]||'未知')+'</b><strong>'+esc(summaries[key]||'阶段性结论待补充')+'</strong></div>'}).join('')+'</div>';
}
function qaImpactFact(label,value){return '<div class="qa-impact-fact"><b>'+label+'</b>'+esc(value||'待核验')+'</div>'}
function qaImpactsHtml(rows){
  const stages=[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']];
  return '<div class="qa-impact-list">'+rows.map(function(row){
    const details=row.horizon_details||{};
    const stageHtml=stages.map(function(item){const key=item[0],label=item[1],direction=(row.horizon_directions||{})[key]||'UNKNOWN',detail=details[key]||{};return '<div class="qa-impact-stage '+qaDirectionClass(direction)+'"><b>'+label+' · '+esc(detail.direction_zh||directionLabelZh[direction]||'未知')+'</b><p>'+esc(detail.detail_zh||'该阶段的经营与财务传导待补充。')+'</p></div>'}).join('');
    return '<article class="qa-impact"><div class="qa-impact-head"><b>'+esc(row.industry_name_zh)+'</b><span class="qa-tier">'+esc(row.impact_tier_zh||tierLabelZh[row.impact_tier]||'影响层级待核验')+'</span></div><div class="qa-impact-facts">'+qaImpactFact('可观察驱动',row.observable_driver_zh)+qaImpactFact('经营变量',row.industry_operating_variable_zh)+qaImpactFact('财务变量',row.industry_financial_variable_zh)+qaImpactFact('传导变化',row.behavior_change_zh)+'</div><div class="qa-impact-stages">'+stageHtml+'</div><div class="qa-boundaries"><span><b>成立条件：</b>'+esc(row.condition_zh||'待核验')+'</span><span><b>失效条件：</b>'+esc(row.invalidation_condition_zh||'待核验')+'</span></div></article>';
  }).join('')+'</div>';
}
function qaRefusalHtml(rows){
  if(!rows.length)return '<div class="qa-boundary">当前未登记强制拒答项，但结论仍保持候选状态并等待人工审核。</div>';
  return '<div class="qa-refusals">'+rows.slice(0,8).map(function(row){return '<div class="qa-refusal"><span>'+esc(row.scope_id)+'</span><b>未知 · 暂不判断 · '+esc(refusalReasonZh[row.refusal_reason]||row.refusal_reason)+'</b></div>'}).join('')+'</div>';
}
renderMain();
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    html = _render_v3(bundle)
    html = html.replace("</head>", CHINESE_DETAIL_STYLE + "</head>")
    return html.replace("</body>", CHINESE_DETAIL_OVERRIDE + "</body>")


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
