"""Integrate the industry research closure into the existing workbench."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_008 import build_ui_bundle as _build_v8
from fingoose_company_impact_qa_ui_v2_impl_008 import render_workbench as _render_v8
from fingoose_industry_research_closure_v3 import enrich_bundle


RESEARCH_STYLE = r"""
<style>
.research-closure{margin-top:22px;border-top:2px solid var(--ink);padding-top:16px}.research-closure-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:12px}.research-closure-head h4{margin:0 0 4px}.research-closure-head p{margin:0;color:var(--muted);font-size:11px}.closure-score{display:grid;grid-template-columns:repeat(3,minmax(58px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);min-width:250px}.closure-score div{background:#fff;padding:8px}.closure-score b{display:block;font-size:15px}.closure-score span{font-size:9px;color:var(--muted)}
.closure-node-list{border-top:1px solid var(--line)}.closure-node{display:grid;grid-template-columns:42px minmax(160px,.28fr) 1fr;gap:12px;padding:11px 0;border-bottom:1px solid var(--line);align-items:start}.closure-step{font-size:10px;color:var(--muted)}.closure-step b{display:block;font-size:17px;color:var(--ink)}.closure-status{font-size:10px;font-weight:800}.closure-status.verified{color:#176b53}.closure-status.supported{color:#84640f}.closure-status.missing{color:#a63f35}.closure-node p{margin:0 0 6px;font-size:11px;line-height:1.6}.closure-node small{display:block;color:var(--muted);line-height:1.5}.closure-evidence-buttons{display:flex;gap:5px;flex-wrap:wrap;margin-top:7px}.closure-evidence-button,.closure-step-button{border:1px solid var(--line);background:#fff;color:var(--teal);font:inherit;font-size:9px;font-weight:800;padding:4px 6px;cursor:pointer}.closure-evidence-button.missing{color:#a63f35;border-style:dashed;cursor:default}
.closure-evidence-registry{margin-top:13px;border-top:1px solid var(--line)}.closure-evidence-entry{display:grid;grid-template-columns:minmax(160px,.25fr) 1fr;gap:14px;padding:12px 0;border-bottom:1px solid var(--line);scroll-margin-top:16px}.closure-evidence-entry.highlight{background:#fff8df;outline:2px solid #b58b23;outline-offset:3px}.closure-evidence-meta b{display:block;font-size:11px;word-break:break-all}.closure-evidence-meta small{display:block;margin-top:4px;color:var(--muted)}.closure-evidence-quote blockquote{margin:0 0 7px;padding-left:10px;border-left:2px solid var(--teal);font-size:11px;line-height:1.65}.closure-evidence-quote a{font-size:10px;color:var(--teal)}
.event-study{margin-top:22px;padding-top:16px;border-top:2px solid var(--ink)}.event-study-summary{display:grid;grid-template-columns:minmax(180px,.6fr) repeat(4,minmax(90px,1fr));border:1px solid var(--line);background:var(--line);gap:1px}.study-method,.study-stat{background:#fff;padding:10px}.study-method b,.study-stat b{display:block}.study-method small,.study-stat small{font-size:9px;color:var(--muted)}.study-stat strong{font-size:15px}.study-stat.positive strong{color:#176b53}.study-stat.negative strong{color:#a63f35}.event-study .table-wrap{margin-top:10px}.event-study-table{width:100%;border-collapse:collapse;font-size:10px}.event-study-table th,.event-study-table td{padding:8px;border-bottom:1px solid var(--line);text-align:right}.event-study-table th:first-child,.event-study-table td:first-child{text-align:left}.robustness-line{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;padding:9px 0;border-top:1px dashed var(--line);font-size:10px}.robustness-line b{color:var(--teal)}.cutoff-gate{margin-top:9px;padding:9px 10px;border-left:3px solid #a63f35;background:#fff4f1;font-size:10px;line-height:1.55}
.industry-company-matrix{margin-top:24px;padding-top:16px;border-top:2px solid var(--ink)}.industry-company-matrix h4{margin:0 0 4px}.industry-company-matrix>p{margin:0 0 10px;color:var(--muted);font-size:11px}.matrix-scroll{max-width:100%;overflow-x:auto;border:1px solid var(--line)}.matrix-table{border-collapse:collapse;width:100%;min-width:980px;font-size:10px}.matrix-table th{position:sticky;top:0;background:#f1f3f0;color:#526063;text-align:left;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}.matrix-table td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}.matrix-table tr.active{background:#f4f8f7}.matrix-industry{border:0;background:transparent;color:var(--teal);font:inherit;font-weight:800;padding:0;cursor:pointer;text-align:left}.matrix-company-list{display:flex;gap:5px;flex-wrap:wrap}.matrix-company{border:1px solid var(--line);background:#fff;color:var(--ink);font:inherit;font-size:9px;padding:4px 6px;cursor:pointer}.matrix-muted{color:var(--muted)}
@media(max-width:760px){.research-closure-head{display:block}.closure-score{margin-top:10px;min-width:0;width:100%}.closure-node{grid-template-columns:34px 1fr}.closure-node>div:last-child{grid-column:2}.closure-evidence-entry{grid-template-columns:1fr}.event-study-summary{grid-template-columns:1fr 1fr}.study-method{grid-column:1/-1}.research-closure,.event-study,.industry-company-matrix{margin-top:18px}.industry-detail{overflow:hidden}.matrix-scroll{overscroll-behavior-x:contain}}
</style>
"""


RESEARCH_OVERRIDE = r"""
<script>
function closureDirectionZh(value){return ({POSITIVE:'偏正',NEGATIVE:'偏负',MIXED:'混合',NEUTRAL:'中性',FLAT:'接近零',UNKNOWN:'未知'})[value]||value||'未知'}
function closureDirectionClass(value){return value==='POSITIVE'?'positive':value==='NEGATIVE'?'negative':''}
function closurePct(value){return value==null?'—':(Number(value)*100).toFixed(2)+'%'}
function closureDomId(value){return 'closure-evidence-'+String(value||'').replace(/[^a-zA-Z0-9_-]/g,'-')}
function closureStatusClass(statusValue){if(statusValue==='VERIFIED_SOURCE')return 'verified';if(statusValue==='EVIDENCE_MISSING')return 'missing';return 'supported'}
function closureEvidenceButtons(node){
  const ids=node.evidence_ids||[];
  if(!ids.length)return '<span class="matrix-muted">本步无直接证据 ID</span>';
  return ids.map(function(id){const missing=(node.missing_evidence_ids||[]).includes(id);return '<button type="button" class="closure-evidence-button '+(missing?'missing':'')+'" data-closure-evidence-id="'+esc(id)+'" '+(missing?'disabled aria-disabled="true"':'')+'>'+esc(id)+(missing?' · 缺证':'')+'</button>'}).join('');
}
function closureNodeHtml(node){
  return '<article class="closure-node" data-closure-node-step="'+node.step+'"><div class="closure-step"><span>步骤</span><b>'+node.step+'</b></div><div><span class="closure-status '+closureStatusClass(node.status)+'">'+esc(node.status_zh)+'</span><small>'+esc(node.node_type)+'</small></div><div><p>'+esc(node.statement_zh)+'</p><small>'+esc(node.boundary_zh)+'</small><div class="closure-evidence-buttons">'+closureEvidenceButtons(node)+'</div></div></article>';
}
function closureEvidenceEntry(row){
  const steps=(row.supports_steps||[]).map(function(step){return '<button type="button" class="closure-step-button" data-closure-node-step-target="'+step+'">步骤 '+step+'</button>'}).join('');
  if(row.missing)return '<article class="closure-evidence-entry" id="'+closureDomId(row.evidence_id)+'" data-closure-evidence-id="'+esc(row.evidence_id)+'"><div class="closure-evidence-meta"><b>'+esc(row.evidence_id)+'</b><small>证据缺口</small></div><div class="closure-evidence-quote"><p>当前候选包未包含可核对的原文、定位与来源链接。</p><div>'+steps+'</div></div></article>';
  return '<article class="closure-evidence-entry" id="'+closureDomId(row.evidence_id)+'" data-closure-evidence-id="'+esc(row.evidence_id)+'"><div class="closure-evidence-meta"><b>'+esc(row.evidence_id)+'</b><small>'+esc(row.publisher||row.title||'来源待标注')+'</small><small>'+esc(row.first_public_at||'首次公开时间待核验')+'</small><small>'+esc(row.locator||'定位待核验')+'</small><small>SHA-256 '+esc(row.snapshot_sha256||'DEFERRED')+'</small></div><div class="closure-evidence-quote"><blockquote>'+esc(row.original_quote||'原文待补')+'</blockquote><div>'+steps+'</div>'+(row.source_url?'<a href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">查看来源原文</a>':'')+'</div></article>';
}
function eventStudyHtml(study){
  const windows=study.windows||{},model=study.market_model||{},robust=study.robustness||{};
  const order=[['PRETREND','事件前趋势'],['EVENT','事件窗口'],['SHORT','短期'],['MEDIUM','中期']];
  const summary=order.map(function(item){const row=windows[item[0]]||{};return '<div class="study-stat '+closureDirectionClass(row.direction)+'"><small>'+item[1]+'</small><strong>'+closurePct(row.market_model_car)+'</strong><b>'+closureDirectionZh(row.direction)+'</b></div>'}).join('');
  const table=order.map(function(item){const row=windows[item[0]]||{};return '<tr data-study-window="'+item[0]+'"><td><b>'+item[0]+'</b><br>'+item[1]+'</td><td>'+esc(row.sample_count)+'</td><td>'+closurePct(row.simple_car)+'</td><td>'+closurePct(row.market_model_car)+'</td><td>'+closurePct(row.average_abnormal_return)+'</td><td>'+closurePct(row.volatility)+'</td><td>'+esc(row.t_value)+'</td><td>'+closureDirectionZh(row.direction)+'</td></tr>'}).join('');
  return '<section class="event-study"><div class="section-head"><div><h4>标准事件研究</h4><p>市场调整法与事件前市场模型并列展示，统计验证不证明因果</p></div></div><div class="event-study-summary"><div class="study-method"><b>估计窗 '+esc(study.estimation_window)+'</b><small>alpha '+esc(model.alpha)+' · beta '+esc(model.beta)+' · n='+esc(model.estimation_count)+'</small></div>'+summary+'</div><div class="table-wrap"><table class="event-study-table"><thead><tr><th>窗口</th><th>样本</th><th>简单 CAR</th><th>模型 CAR</th><th>平均异常</th><th>波动率</th><th>t 值</th><th>方向</th></tr></thead><tbody>'+table+'</tbody></table></div><div class="robustness-line"><span><b>安慰剂百分位</b> '+(Number(robust.event_abs_car_percentile||0)*100).toFixed(1)+'%</span><span><b>模型方向</b> '+(robust.model_direction_consistent?'一致':'不一致')+'</span><span><b>事件前趋势</b> '+(robust.pretrend_contaminated?'存在污染风险':'未触发阈值')+'</span><span><b>安慰剂窗口</b> '+esc((robust.placebo_windows||[]).length)+' 个</span></div><div class="'+(study.cutoff_blocked?'cutoff-gate':'notice')+'">'+esc(study.interpretation_zh)+'</div></section>';
}
function industryCompanyMatrix(event){
  const rows=event.industry_company_matrix||[];
  const body=rows.map(function(row){const directions=row.industry_horizon_directions||{};const companies=(row.companies||[]).map(function(company){const companyDirections=company.horizon_directions||{};const title=(company.selection_reason_zh||'')+' '+(company.confounder_summary_zh||'');return '<button type="button" class="matrix-company" data-matrix-company="'+esc(company.company_id)+'" title="'+esc(title)+'">'+esc(company.company_name)+' · '+closureDirectionZh(companyDirections.IMMEDIATE)+'/'+closureDirectionZh(companyDirections.SHORT_TERM)+'/'+closureDirectionZh(companyDirections.MEDIUM_TERM)+'</button>'}).join('')||'<span class="matrix-muted">未配置公司样本</span>';return '<tr class="'+(row.event_industry_mapping_id===state.industryMappingId?'active':'')+'"><td><button type="button" class="matrix-industry" data-matrix-industry="'+esc(row.event_industry_mapping_id)+'" data-matrix-tier="'+esc(row.impact_tier)+'">'+esc(row.industry_name_zh)+'</button><br><span class="matrix-muted">'+esc(row.impact_tier)+'</span></td><td>'+closureDirectionZh(directions.IMMEDIATE)+'</td><td>'+closureDirectionZh(directions.SHORT_TERM)+'</td><td>'+closureDirectionZh(directions.MEDIUM_TERM)+'</td><td>'+Math.round(Number(row.evidence_coverage_ratio||0)*100)+'%</td><td>'+closurePct(row.event_car)+'<br><span class="matrix-muted">'+closureDirectionZh(row.event_car_direction)+'</span></td><td>'+(Number(row.robustness_percentile||0)*100).toFixed(1)+'%'+(row.cutoff_blocked?'<br><span class="closure-status missing">截止日拒答</span>':'')+'</td><td><div class="matrix-company-list">'+companies+'</div></td></tr>'}).join('');
  return '<section class="industry-company-matrix"><h4>行业—公司联动矩阵</h4><p>横向比较七步证据覆盖、三阶段方向、事件窗口 CAR 与固定公司样本；点击可联动现有详情。</p><div class="matrix-scroll"><table class="matrix-table"><thead><tr><th>行业 / 层级</th><th>即时</th><th>短期</th><th>中期</th><th>证据覆盖</th><th>事件 CAR</th><th>稳健性百分位</th><th>关联公司</th></tr></thead><tbody>'+body+'</tbody></table></div></section>';
}
function industryResearchWorkspace(event){
  const impact=selectedIndustryImpact(event);if(!impact||!impact.research_closure)return '';
  const closure=impact.research_closure,registry=closure.evidence_registry||[];
  return '<section class="research-closure"><div class="research-closure-head"><div><h4>七步链证据闭环</h4><p>逐节点区分原文、研究推断与证据缺口；证据 ID 可与原文双向定位。</p></div><div class="closure-score"><div><b>'+closure.verified_count+'</b><span>原文已定位</span></div><div><b>'+closure.inference_count+'</b><span>研究推断</span></div><div><b>'+closure.missing_count+'</b><span>证据缺口</span></div></div></div><div class="closure-node-list">'+(closure.node_statuses||[]).map(closureNodeHtml).join('')+'</div><div class="closure-evidence-registry"><h4>证据原文登记</h4>'+registry.map(closureEvidenceEntry).join('')+'</div></section>'+eventStudyHtml(closure.event_study||{})+industryCompanyMatrix(event);
}
window.industryResearchWorkspace=industryResearchWorkspace;
window.industryCompanyMatrix=industryCompanyMatrix;
const industryDetailImpl008=window.industryDetail;
window.industryDetail=function(event){return industryDetailImpl008(event)+industryResearchWorkspace(event)};
industryDetail=window.industryDetail;
function bindIndustryResearchClosure(){
  document.querySelectorAll('.closure-evidence-button:not(.missing)').forEach(function(button){button.onclick=function(){document.querySelectorAll('.closure-evidence-entry.highlight').forEach(function(row){row.classList.remove('highlight')});const target=document.getElementById(closureDomId(button.dataset.closureEvidenceId));if(target){target.classList.add('highlight');target.scrollIntoView({behavior:'smooth',block:'center'})}}});
  document.querySelectorAll('[data-closure-node-step-target]').forEach(function(button){button.onclick=function(){const target=document.querySelector('[data-closure-node-step="'+button.dataset.closureNodeStepTarget+'"]');if(target)target.scrollIntoView({behavior:'smooth',block:'center'})}});
  document.querySelectorAll('[data-matrix-industry]').forEach(function(button){button.onclick=function(){state.industryMappingId=button.dataset.matrixIndustry;state.industryTier=button.dataset.matrixTier;state.transmissionMode='industry';renderMain();const target=document.querySelector('.research-closure');if(target)target.scrollIntoView({block:'start'})}});
  document.querySelectorAll('[data-matrix-company]').forEach(function(button){button.onclick=function(){state.companyId=button.dataset.matrixCompany;renderMain();const target=document.getElementById('companies');if(target)target.scrollIntoView({block:'start'})}});
}
window.bindIndustryResearchClosure=bindIndustryResearchClosure;
const bindQaImpl008=window.bindQa;
window.bindQa=function(){bindQaImpl008();bindIndustryResearchClosure()};
bindQa=window.bindQa;
renderMain();
</script>
"""


def build_ui_bundle(root: Path, **kwargs: Any) -> dict[str, Any]:
    return dict(enrich_bundle(_build_v8(root, **kwargs)))


def render_workbench(bundle: Mapping[str, Any]) -> str:
    enriched = enrich_bundle(dict(bundle))
    html = _render_v8(enriched)
    html = html.replace("</head>", RESEARCH_STYLE + "</head>")
    return html.replace("</body>", RESEARCH_OVERRIDE + "</body>")


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


if __name__ == "__main__":
    raise SystemExit(main())
