"""Add full evidence controls, lineage, strength, selection reasons, and horizon views."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_001 import build_ui_bundle
from fingoose_company_impact_qa_ui_v2_impl_007 import render_workbench as _render_v7


REFINEMENT_STYLE = r"""
<style>
.qa-filterbar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0;padding:8px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.qa-filterbar label{font-size:10px;font-weight:800;color:var(--muted)}.qa-filterbar select,.qa-filterbar input{height:32px;border:1px solid var(--line);background:#fff;color:var(--ink);font:inherit;font-size:11px;padding:0 8px}.qa-filterbar input{min-width:210px;flex:1}.qa-result-count{font-size:10px;color:var(--muted);margin-left:auto}.qa-evidence-lineage{margin-top:9px;padding-top:7px;border-top:1px dashed var(--line);font-size:10px;color:#526063;line-height:1.55}.qa-evidence-lineage b{color:var(--teal)}
.qa-refusal-detail{border-bottom:1px solid var(--line);padding:9px 0}.qa-refusal-detail summary{cursor:pointer;display:grid;grid-template-columns:minmax(160px,.6fr) 1fr;gap:10px;font-size:11px}.qa-refusal-detail summary::-webkit-details-marker{display:none}.qa-refusal-detail p{margin:7px 0 0;padding-left:10px;border-left:2px solid var(--gold);font-size:11px;color:#465356}.qa-refusal-detail[hidden],.qa-evidence[hidden]{display:none}
.qa-horizon-switch{display:flex;align-items:center;gap:0;margin:12px 0;border-bottom:1px solid var(--line)}.qa-horizon-switch span{font-size:10px;color:var(--muted);margin-right:10px}.qa-horizon-switch button{border:0;border-top:2px solid transparent;background:transparent;color:#526063;font:inherit;font-size:11px;font-weight:800;padding:9px 12px;cursor:pointer}.qa-horizon-switch button.active{border-top-color:var(--gold);color:var(--ink);background:var(--soft)}.qa-stage-hidden{display:none!important}.qa-strength-legend{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 12px;font-size:10px;color:var(--muted)}.qa-strength{display:inline-block;margin-top:4px;color:var(--teal);font-weight:800}.qa-selection-reasons{display:grid;gap:6px}.qa-selection-reason{display:grid;grid-template-columns:minmax(90px,.25fr) 1fr;gap:10px;padding:8px 0;border-bottom:1px dashed var(--line);font-size:11px;line-height:1.55}.qa-selection-reason b{color:var(--teal)}
@media(max-width:760px){.qa-filterbar{align-items:stretch}.qa-filterbar input{min-width:100%;width:100%}.qa-result-count{width:100%;margin-left:0}.qa-horizon-switch{overflow-x:auto}.qa-horizon-switch span{display:none}.qa-horizon-switch button{white-space:nowrap;flex:1}.qa-refusal-detail summary,.qa-selection-reason{grid-template-columns:1fr}}
</style>
"""


REFINEMENT_OVERRIDE = r"""
<script>
function qaEvidenceFilter(rows){
  const tiers=[];(rows||[]).forEach(function(row){const tier=row.source_tier||'未分级';if(!tiers.includes(tier))tiers.push(tier)});
  return '<div class="qa-filterbar"><label for="qa-evidence-tier">证据级别</label><select id="qa-evidence-tier"><option value="ALL">全部</option>'+tiers.map(function(tier){return '<option value="'+esc(tier)+'">'+esc(tier)+'</option>'}).join('')+'</select><label for="qa-evidence-query">检索</label><input id="qa-evidence-query" type="search" placeholder="来源、中文事实或证据 ID"><span class="qa-result-count" id="qa-evidence-count">共 '+rows.length+' 条</span></div>';
}
window.qaEvidenceHtml=function(rows){
  rows=rows||[];
  if(!rows.length)return '<div class="empty">截止日前没有满足原文、定位符与直达链接合同的证据。</div>';
  return qaEvidenceFilter(rows)+'<div class="qa-evidence-grid">'+rows.map(function(row){const tier=row.source_tier||'未分级';const search=[row.publisher_zh,row.publisher,row.fact_zh,row.original_quote,row.evidence_id].filter(Boolean).join(' ').toLowerCase();return '<article class="qa-evidence" data-evidence-tier="'+esc(tier)+'" data-evidence-search="'+esc(search)+'"><div class="qa-evidence-head"><b>'+esc(row.publisher_zh||row.publisher||row.evidence_id)+'</b><span class="chip">'+esc(tier)+'</span></div><h4>中文事实摘录</h4><p class="fact-zh">'+esc(row.fact_zh||row.original_quote)+'</p><small>'+esc(row.locator_zh||row.locator||'定位待核验')+' · 首次公开 '+esc(row.first_public_at||row.published_at)+'</small><details class="qa-source-original"><summary>展开审计原文与哈希</summary><blockquote>'+esc(row.original_quote)+'</blockquote><small>证据 ID：'+esc(row.evidence_id)+'</small><small>原始定位：'+esc(row.locator||row.locator_zh||'待核验')+'</small><small>SHA-256 '+esc(row.snapshot_sha256||'待补')+'</small></details><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看官方原文</a></article>'}).join('')+'</div>';
};
qaEvidenceHtml=window.qaEvidenceHtml;
function qaRefusalFilter(rows){return '<div class="qa-filterbar"><label for="qa-refusal-scope">拒答范围</label><select id="qa-refusal-scope"><option value="ALL">全部</option><option value="EVENT">事件</option><option value="INDUSTRY">行业</option><option value="COMPANY">公司</option></select><span class="qa-result-count" id="qa-refusal-count">共 '+rows.length+' 项</span></div>'}
function qaRefusalScope(row){const id=String(row.scope_id||'').toLowerCase();if(id.includes('company'))return 'COMPANY';if(id.includes('industry'))return 'INDUSTRY';return 'EVENT'}
window.qaRefusalHtml=function(rows){
  rows=rows||[];
  if(!rows.length)return '<div class="qa-boundary">当前未登记强制拒答项，但结论仍保持候选状态并等待人工审核。</div>';
  return qaRefusalFilter(rows)+'<div class="qa-refusals">'+rows.map(function(row){const scope=qaRefusalScope(row);return '<details class="qa-refusal-detail" data-refusal-scope="'+scope+'"><summary><span>'+esc(row.scope_id)+'</span><b>未知 · 暂不判断 · '+esc(refusalReasonZh[row.refusal_reason]||row.refusal_reason)+'</b></summary><p>该范围维持 '+esc(row.decision||'ABSTAIN')+'，方向为 '+esc(row.direction||'UNKNOWN')+'；需补证或人工关闭后才能提升结论。</p></details>'}).join('')+'</div>';
};
qaRefusalHtml=window.qaRefusalHtml;
window.qaImpactsHtml=function(rows){
  const stages=[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']];
  return '<div class="qa-impact-list">'+(rows||[]).map(function(row){const details=row.horizon_details||{};const stageHtml=stages.map(function(item){const key=item[0],label=item[1],direction=(row.horizon_directions||{})[key]||'UNKNOWN',detail=details[key]||{};return '<div class="qa-impact-stage '+qaDirectionClass(direction)+'" data-impact-horizon="'+key+'"><b>'+label+' · '+esc(detail.direction_zh||directionLabelZh[direction]||'未知')+'</b><p>'+esc(detail.detail_zh||'该阶段的经营与财务传导待补充。')+'</p></div>'}).join('');const ids=row.research_evidence_ids||[];return '<article class="qa-impact"><div class="qa-impact-head"><b>'+esc(row.industry_name_zh)+'</b><span class="qa-tier">'+esc(row.impact_tier_zh||tierLabelZh[row.impact_tier]||'影响层级待核验')+'</span></div><div class="qa-impact-facts">'+qaImpactFact('可观察驱动',row.observable_driver_zh)+qaImpactFact('经营变量',row.industry_operating_variable_zh)+qaImpactFact('财务变量',row.industry_financial_variable_zh)+qaImpactFact('传导变化',row.behavior_change_zh)+'</div><div class="qa-impact-stages">'+stageHtml+'</div><div class="qa-evidence-lineage"><b>研究证据 ID</b> '+esc(ids.join('、')||'待补证')+'<br>'+esc(row.evidence_lineage_zh||'行业推断保持候选状态。')+'</div><div class="qa-boundaries"><span><b>成立条件：</b>'+esc(row.condition_zh||'待核验')+'</span><span><b>失效条件：</b>'+esc(row.invalidation_condition_zh||'待核验')+'</span></div></article>'}).join('')+'</div>';
};
qaImpactsHtml=window.qaImpactsHtml;
const qaMarketValidationAnswerImpl007=window.qaMarketValidationAnswer;
window.qaMarketValidationAnswer=function(answer){
  const task=answer.task_answer||{},rows=task.industry_results||[];
  return '<article class="qa-task-block"><h3>验证口径</h3><p>'+esc(task.method_zh||'行情验证口径待补充')+'</p><div class="qa-strength-legend"><b>统计强度：</b><span>统计偏弱 &lt; 2%</span><span>统计中等 2%–5%</span><span>统计较强 ≥ 5%</span><span>仅表示相对收益幅度，不证明因果</span></div></article><article class="qa-task-block"><h3>行业结果与阶段判定</h3><p>展开行业查看六个固定窗口；方向判定与统计强度分开显示。</p><div class="qa-market-results">'+rows.map(function(row){const verdicts=row.horizon_verdicts||{};return '<details class="qa-market-result"><summary><span>'+esc(row.industry_name_zh||row.event_industry_mapping_id)+'</span><span class="qa-verdict '+qaVerdictClass(row.overall_verdict)+'">总体 '+esc(row.overall_verdict_zh||row.overall_verdict)+'</span></summary><div class="qa-verdict-grid">'+[['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']].map(function(item){const verdict=verdicts[item[0]]||{};return '<div class="qa-verdict-item"><b>'+item[1]+' · '+esc(verdict.verdict_zh||'待判定')+'</b><span class="qa-strength">'+esc(verdict.strength_zh||'不可评估')+'</span><br>'+esc(verdict.basis_zh||'判定依据待补充')+'</div>'}).join('')+'</div>'+qaIndustryWindowsTable(row)+'</details>'}).join('')+'</div></article>';
};
qaMarketValidationAnswer=window.qaMarketValidationAnswer;
const qaIndustryCompanyAnswerImpl007=window.qaIndustryCompanyAnswer;
window.qaIndustryCompanyAnswer=function(answer){const rows=(answer.task_answer||{}).company_results||[];return '<article class="qa-task-block"><h3>样本入选理由</h3><p>三家公司按事件前暴露披露、行业代表性、证据可追溯性与交易状态选取，不按事后股价筛选。</p><div class="qa-selection-reasons">'+rows.map(function(row){return '<div class="qa-selection-reason"><b>'+esc(row.company_name)+'</b><span>'+esc(row.selection_reason_zh||'入选理由待补充')+'</span></div>'}).join('')+'</div></article>'+qaIndustryCompanyAnswerImpl007(answer)};
qaIndustryCompanyAnswer=window.qaIndustryCompanyAnswer;
const qaMainReasoningAnswerImpl007=window.qaMainReasoningAnswer;
function qaHorizonSwitch(){const active=state.qaHorizonView||'ALL';return '<div class="qa-horizon-switch" role="tablist" aria-label="研究阶段切换"><span>阶段视图</span>'+[['ALL','全部'],['IMMEDIATE','即时'],['SHORT_TERM','短期'],['MEDIUM_TERM','中期']].map(function(item){return '<button type="button" data-horizon-view="'+item[0]+'" class="'+(active===item[0]?'active':'')+'" role="tab" aria-selected="'+(active===item[0])+'">'+item[1]+'</button>'}).join('')+'</div>'}
window.qaMainReasoningAnswer=function(answer){return qaHorizonSwitch()+qaMainReasoningAnswerImpl007(answer)};
qaMainReasoningAnswer=window.qaMainReasoningAnswer;
function applyQaHorizonView(view){state.qaHorizonView=view;const order=['IMMEDIATE','SHORT_TERM','MEDIUM_TERM'];document.querySelectorAll('[data-horizon-view]').forEach(function(button){const active=button.dataset.horizonView===view;button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active))});document.querySelectorAll('.qa-stage-reason').forEach(function(card,index){card.classList.toggle('qa-stage-hidden',view!=='ALL'&&order[index]!==view)});document.querySelectorAll('[data-impact-horizon]').forEach(function(card){card.classList.toggle('qa-stage-hidden',view!=='ALL'&&card.dataset.impactHorizon!==view)})}
function bindQaEvidenceControls(){const tier=document.getElementById('qa-evidence-tier'),query=document.getElementById('qa-evidence-query');if(!tier||!query)return;const apply=function(){let visible=0;document.querySelectorAll('.qa-evidence').forEach(function(card){const showTier=tier.value==='ALL'||card.dataset.evidenceTier===tier.value;const showText=!query.value||String(card.dataset.evidenceSearch||'').includes(query.value.trim().toLowerCase());card.hidden=!(showTier&&showText);if(!card.hidden)visible+=1});const count=document.getElementById('qa-evidence-count');if(count)count.textContent='显示 '+visible+' 条'};tier.onchange=apply;query.oninput=apply;apply()}
function bindQaRefusalControls(){const select=document.getElementById('qa-refusal-scope');if(!select)return;const apply=function(){let visible=0;document.querySelectorAll('.qa-refusal-detail').forEach(function(row){row.hidden=!(select.value==='ALL'||row.dataset.refusalScope===select.value);if(!row.hidden)visible+=1});const count=document.getElementById('qa-refusal-count');if(count)count.textContent='显示 '+visible+' 项'};select.onchange=apply;apply()}
const bindQaImpl007=window.bindQa;
window.bindQa=function(){bindQaImpl007();bindQaEvidenceControls();bindQaRefusalControls();document.querySelectorAll('[data-horizon-view]').forEach(function(button){button.onclick=function(){applyQaHorizonView(button.dataset.horizonView)}});applyQaHorizonView(state.qaHorizonView||'ALL')};
bindQa=window.bindQa;
renderMain();
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    html = _render_v7(bundle)
    html = html.replace("</head>", REFINEMENT_STYLE + "</head>")
    return html.replace("</body>", REFINEMENT_OVERRIDE + "</body>")


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
