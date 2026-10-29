"""Company-impact UI projection with evidence-closed confounder details."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import _fingoose_company_impact_ui_v2_base as _base
from fingoose_company_impact_io_v2 import read_jsonl


def _by_mapping(path: Path) -> dict[str, dict[str, Any]]:
    return {str(row["mapping_id"]): row for row in read_jsonl(path)}


def _by_industry_mapping(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {str(row["event_industry_mapping_id"]): row for row in rows}


def _load_industry_layer(industry_root: Path) -> dict[str, list[dict[str, Any]]]:
    names = {
        "mappings": "event_industry_mappings.jsonl",
        "chains": "industry_mechanism_chains.jsonl",
        "evidence": "industry_evidence.jsonl",
        "drivers": "industry_driver_registry.jsonl",
        "observations": "industry_driver_observations.jsonl",
        "windows": "industry_market_windows.jsonl",
        "completion": "industry_completion_report.jsonl",
        "fetches": "industry_source_fetches.jsonl",
    }
    if not industry_root.exists():
        return {key: [] for key in names}
    return {
        key: (
            read_jsonl(industry_root / filename)
            if (industry_root / filename).exists()
            else []
        )
        for key, filename in names.items()
    }


def _merge_industry_layers(
    base: Mapping[str, list[dict[str, Any]]],
    overlay: Mapping[str, list[dict[str, Any]]],
    *,
    overlay_source: str,
    event_scope: set[str],
) -> dict[str, list[dict[str, Any]]]:
    merged = {key: [dict(row) for row in rows] for key, rows in base.items()}
    overlay_events = {
        str(row["event_industry_mapping_id"]): str(row["event_id"])
        for row in overlay.get("mappings", [])
    }
    for key in ("mappings", "chains", "drivers", "windows", "completion"):
        by_id = {
            str(row["event_industry_mapping_id"]): dict(row)
            for row in merged[key]
        }
        for row in overlay.get(key, []):
            mapping_id = str(row["event_industry_mapping_id"])
            event_id = str(row.get("event_id") or overlay_events.get(mapping_id) or "")
            if event_id not in event_scope or mapping_id not in by_id:
                raise ValueError(f"INVALID_INDUSTRY_OVERLAY_ID:{mapping_id}")
            by_id[mapping_id] = {
                **by_id[mapping_id],
                **dict(row),
                "overlay_source": overlay_source,
            }
        merged[key] = list(by_id.values())
    base_evidence = {
        str(row["evidence_id"]): dict(row) for row in merged["evidence"]
    }
    base_evidence.update(
        {
            str(row["evidence_id"]): dict(row)
            for row in overlay.get("evidence", [])
        }
    )
    merged["evidence"] = list(base_evidence.values())
    for key, id_field in (
        ("observations", "observation_id"),
        ("fetches", "source_id"),
    ):
        by_id = {
            str(row.get(id_field) or json.dumps(row, sort_keys=True)): dict(row)
            for row in merged.get(key, [])
        }
        by_id.update(
            {
                str(row.get(id_field) or json.dumps(row, sort_keys=True)): dict(row)
                for row in overlay.get(key, [])
            }
        )
        merged[key] = list(by_id.values())
    return merged


def _default_industry_overlays(root: Path) -> list[tuple[Path, str, set[str]]]:
    contract_path = root / "configs/industry_impact_v2/multi_event_closure_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    overlays: list[tuple[Path, str, set[str]]] = []
    for item in contract.get("overlay_order", []):
        event_scope = {str(value) for value in item.get("event_scope") or []}
        overlay_source = (
            "EVENT_01_CLOSURE"
            if event_scope == {"event-01"}
            else "EVENT_02_10_CLOSURE"
        )
        overlays.append((root / str(item["path"]), overlay_source, event_scope))
    return overlays


def _attach_industry_layer(
    bundle: dict[str, Any],
    industry_rows: Mapping[str, list[dict[str, Any]]],
) -> None:
    chains = _by_industry_mapping(industry_rows["chains"])
    drivers = _by_industry_mapping(industry_rows["drivers"])
    windows = _by_industry_mapping(industry_rows["windows"])
    completion = _by_industry_mapping(industry_rows["completion"])
    evidence_by_id = {
        str(row["evidence_id"]): row for row in industry_rows["evidence"]
    }
    observations_by_series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in industry_rows.get("observations", []):
        observations_by_series[str(row["driver_series_id"])].append(dict(row))
    tier_order = {"CORE_DIRECT": 0, "SECOND_ORDER": 1, "CONDITIONAL": 2}
    by_event: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for source in industry_rows["mappings"]:
        mapping = dict(source)
        mapping_id = str(mapping["event_industry_mapping_id"])
        chain_source = chains.get(mapping_id)
        chain = dict(chain_source) if chain_source else None
        evidence_ids: set[str] = {
            str(value) for value in mapping.get("event_evidence_ids") or []
        }
        if chain:
            chain_nodes = []
            conditions: list[str] = []
            invalidations: list[str] = []
            for raw_node in chain.get("nodes", []):
                node = dict(raw_node)
                node_evidence_ids = [
                    str(value) for value in node.get("evidence_ids") or []
                ]
                evidence_ids.update(node_evidence_ids)
                node["evidence"] = [
                    evidence_by_id[evidence_id]
                    for evidence_id in node_evidence_ids
                    if evidence_id in evidence_by_id
                ]
                if node.get("condition_zh"):
                    conditions.append(str(node["condition_zh"]))
                if node.get("invalidation_zh"):
                    invalidations.append(str(node["invalidation_zh"]))
                chain_nodes.append(node)
            chain["nodes"] = chain_nodes
            chain_confounders = []
            for raw_confounder in chain.get("confounders", []):
                confounder = dict(raw_confounder)
                confounder_evidence_ids = [
                    str(value) for value in confounder.get("evidence_ids") or []
                ]
                evidence_ids.update(confounder_evidence_ids)
                confounder["evidence"] = [
                    evidence_by_id[evidence_id]
                    for evidence_id in confounder_evidence_ids
                    if evidence_id in evidence_by_id
                ]
                chain_confounders.append(confounder)
            chain["confounders"] = chain_confounders
            chain["conditions_zh"] = list(dict.fromkeys(conditions))
            chain["invalidation_conditions_zh"] = list(
                dict.fromkeys(invalidations)
            )
        driver_source = drivers.get(mapping_id)
        driver = dict(driver_source) if driver_source else None
        if driver:
            driver["observations"] = observations_by_series.get(
                str(driver.get("driver_series_id")), []
            )
        mapping["mechanism_chain"] = chain
        mapping["driver"] = driver
        mapping["market_window"] = windows.get(mapping_id)
        mapping["completion"] = completion.get(mapping_id)
        mapping["evidence"] = [
            evidence_by_id[evidence_id]
            for evidence_id in sorted(evidence_ids)
            if evidence_id in evidence_by_id
        ]
        by_event[str(mapping["event_id"])].append(mapping)

    for event in bundle["events"]:
        impacts = by_event.get(str(event["event_id"]), [])
        impacts.sort(
            key=lambda row: (
                tier_order.get(str(row.get("impact_tier")), 99),
                str(row.get("sw1_id")),
            )
        )
        event["industry_impacts"] = impacts
        event["industry_mechanism_chains"] = [
            row["mechanism_chain"]
            for row in impacts
            if row.get("mechanism_chain")
        ]
        used_evidence_ids = {
            str(row["evidence_id"])
            for impact in impacts
            for row in impact.get("evidence") or []
        }
        event["industry_evidence"] = [
            row
            for row in industry_rows["evidence"]
            if str(row.get("evidence_id")) in used_evidence_ids
        ]
        event["industry_drivers"] = [
            row["driver"] for row in impacts if row.get("driver")
        ]
        event["industry_market_windows"] = [
            row["market_window"] for row in impacts if row.get("market_window")
        ]
        event["industry_completion_reports"] = [
            row["completion"] for row in impacts if row.get("completion")
        ]
        event["summary"]["industry_mapping_count"] = len(impacts)

    bundle["summary"]["industry_mapping_count"] = sum(
        len(event["industry_impacts"]) for event in bundle["events"]
    )


def build_ui_bundle(
    root: Path,
    *,
    candidate_root: Path | None = None,
    industry_root: Path | None = None,
    industry_overlay_root: Path | None = None,
    industry_overlay_roots: list[Path] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    fallback = root / "work/company_impact_high_quality_v2_candidate"
    candidate = (candidate_root or fallback).resolve()
    bundle = _base.build_ui_bundle(root, candidate_root=candidate)
    industry_candidate = (
        industry_root
        or root / "work/industry_impact_high_quality_v2_candidate"
    ).resolve()
    industry_layer = _load_industry_layer(industry_candidate)
    if industry_overlay_root is not None:
        overlay_candidates = [
            (
                industry_overlay_root.resolve(),
                "EVENT_01_CLOSURE",
                {"event-01"},
            )
        ]
    elif industry_overlay_roots is not None:
        overlay_candidates = []
        for path in industry_overlay_roots:
            resolved = path.resolve()
            layer = _load_industry_layer(resolved)
            scope = {str(row.get("event_id")) for row in layer["mappings"]}
            source = (
                "EVENT_01_CLOSURE"
                if scope == {"event-01"}
                else "EVENT_02_10_CLOSURE"
            )
            overlay_candidates.append((resolved, source, scope))
    else:
        overlay_candidates = _default_industry_overlays(root)
    overlay_versions: list[str] = []
    for overlay_candidate, overlay_source, event_scope in overlay_candidates:
        if not overlay_candidate.exists():
            continue
        industry_layer = _merge_industry_layers(
            industry_layer,
            _load_industry_layer(overlay_candidate),
            overlay_source=overlay_source,
            event_scope=event_scope,
        )
        summary_path = overlay_candidate / "summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary.get("dataset_version"):
                overlay_versions.append(str(summary["dataset_version"]))
    _attach_industry_layer(bundle, industry_layer)
    bundle["summary"]["industry_overlay_versions"] = overlay_versions
    arguments = _by_mapping(candidate / "company_confounder_arguments.jsonl")
    searches = _by_mapping(candidate / "company_confounder_search_audits.jsonl")
    trading = _by_mapping(candidate / "trading_status_reviews.jsonl")
    counters = _by_mapping(candidate / "company_counterevidence_reviews.jsonl")
    bodies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(candidate / "announcement_body_reviews.jsonl"):
        bodies[str(row["mapping_id"])].append(row)
    for event in bundle["events"]:
        for company in event["companies"]:
            mapping_id = str(company["mapping_id"])
            company["confounder_argument"] = arguments[mapping_id]
            company["confounder_search_audit"] = searches[mapping_id]
            company["trading_status_review"] = trading[mapping_id]
            company["counterevidence_review"] = counters[mapping_id]
            company["announcement_body_reviews"] = bodies.get(mapping_id, [])
    return bundle


def project_event(bundle: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    return _base.project_event(bundle, event_id)


CONFOUNDER_OVERRIDE = r"""
<script>
function confounderHtml(company){
  const record=company.confounders||{};
  const argument=company.confounder_argument||{};
  const search=company.confounder_search_audit||{};
  const trading=company.trading_status_review||{};
  const counter=company.counterevidence_review||{};
  const bodies=company.announcement_body_reviews||[];
  const stateName=record.display_state||argument.display_state||'UNRESOLVED';
  const stateTitle=stateName==='REVIEWED'?'完整审核论证':stateName==='SEARCH_COMPLETE_NO_MATERIAL_CONFOUNDER'?'完成负向检索，未发现实质混杂':'仍有证据缺口';
  const unresolved=(record.unresolved_reasons||[]).map(item=>`<li>${esc(item)}</li>`).join('');
  const argumentHtml=argument.argument_zh?`<div class="confounder-argument"><b>${esc(stateTitle)} · ${esc(status(record.overall_grade))}</b><p>${esc(argument.argument_zh)}</p></div>`:`<div class="empty">缺少映射级混杂论证。</div>`;
  const reviewed=bodies.filter(item=>['RELEVANT','MINOR_RELEVANCE'].includes(item.relevance_decision));
  const bodyHtml=reviewed.length?reviewed.map(item=>`<div class="confounder-item"><b>${esc(item.announcement_title)}</b><p>${esc(item.original_quote)}</p><small>${esc(item.body_locator)} · 首次公开 ${esc(item.first_public_at)} · 影响窗口 ${esc((item.affected_windows||[]).join('、'))} · ${esc(status(item.severity_candidate))}</small><br><a class="evidence-link" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">打开官方公告正文</a></div>`).join(''):`<div class="negative-audit"><b>负向检索依据</b><p>${esc(search.negative_result_basis||'固定分类检索已完成，未形成正文级实质候选。')}</p><small>${esc(search.window_start)} 至 ${esc(search.window_end)} · ${fmt(search.title_count)} 条标题 · ${fmt(search.candidate_count)} 条正文候选 · ${esc(status(search.search_status))}</small></div>`;
  const windows=trading.window_reviews||{};
  const tradingHtml=`<div class="confounder-meta"><b>可交易性核验</b><p>${esc(trading.verification_basis||'核验依据待补')}</p><span class="chips">${Object.entries(windows).map(([key,value])=>`<span class="chip">${esc(key)} ${esc(value.actual_date||'日期缺失')} · ${esc(status(value.status))}</span>`).join('')}</span></div>`;
  const counterHtml=(counter.findings||[]).slice(0,4).map(item=>`<div class="counter-item"><b>${esc(item.claim_zh)}</b><p>${esc(item.original_quote)}</p><small>${esc(item.locator)} · 影响期限 ${esc((item.affected_horizons||[]).join('、'))}</small><br><a class="evidence-link" href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">打开反证来源</a></div>`).join('')||`<div class="negative-audit"><b>公司级反证负向检索</b><p>${esc(counter.negative_search_basis||'检索记录缺失')}</p></div>`;
  const unresolvedHtml=unresolved?`<div class="notice"><b>未关闭项目</b><ul>${unresolved}</ul></div>`:'';
  return `${argumentHtml}${unresolvedHtml}<div class="confounder-subhead">公告正文与检索审计</div>${bodyHtml}${tradingHtml}<div class="confounder-subhead">公司级反证</div>${counterHtml}<details class="raw-details"><summary>检索与审核技术详情</summary><div class="raw-details-body"><p><code>${esc(search.search_audit_id||'search-audit-missing')}</code></p><p><code>${esc(trading.trading_review_id||'trading-review-missing')}</code></p><p><code>${esc(counter.counterevidence_review_id||'counter-review-missing')}</code></p></div></details>`;
}
renderMain();
</script>
"""


INDUSTRY_STYLE = r"""
<style>
.transmission-tabs{grid-template-columns:repeat(3,minmax(120px,1fr))}
.industry-tier-tabs{display:flex;flex-wrap:wrap;gap:6px;flex:1 0 100%;margin-bottom:14px}
.industry-tier-button{border:1px solid var(--line);background:#fff;color:var(--muted);padding:7px 11px;cursor:pointer;font:inherit;font-weight:700}
.industry-tier-button.active{border-color:var(--ink);background:var(--ink);color:#fff}
.industry-tier-groups{display:grid;gap:22px;flex:1 0 100%}
.industry-tier-group{min-width:0;scroll-margin-top:76px}
.industry-tier-group-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:8px;padding-bottom:7px;border-bottom:1px solid var(--line)}
.industry-tier-group-head h3{margin:0;font-size:16px}.industry-tier-group-head p{margin:0;color:var(--muted);font-size:11px}
.industry-card-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.industry-impact-button{min-width:0;min-height:190px;border:1px solid var(--line);border-top:3px solid #87928f;background:var(--paper);padding:12px;text-align:left;cursor:pointer;color:inherit}
.industry-impact-button[data-tier="CORE_DIRECT"]{border-top-color:var(--accent)}
.industry-impact-button[data-tier="SECOND_ORDER"]{border-top-color:var(--teal)}
.industry-impact-button[data-tier="CONDITIONAL"]{border-top-color:var(--gold)}
.industry-impact-button:hover,.industry-impact-button.active{box-shadow:inset 0 -3px var(--teal);border-color:var(--teal)}
.industry-impact-button h3{margin:2px 0 6px;font-size:15px}.industry-impact-button p{margin:0;color:var(--muted);font-size:12px}.industry-impact-button small{display:block;margin-top:8px;color:var(--muted)}
.industry-gates{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:10px}
.industry-gate{min-width:0;padding:6px 7px;background:var(--soft);font-size:10px;color:var(--muted);overflow-wrap:anywhere}.industry-gate b{display:block;color:var(--ink);font-size:11px}
.industry-chain-group{display:grid;gap:10px;scroll-margin-top:76px}.industry-chain-group+.industry-chain-group{margin-top:8px}
.industry-chain-group-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 12px;background:#e8ece9;border-left:4px solid var(--ink)}
.industry-chain-group-head h3{margin:0;font-size:15px}.industry-chain-group-head span{color:var(--muted);font-size:11px}
.industry-chain-card{border-left-color:var(--gold)}.industry-chain-card.active{border-color:var(--teal);box-shadow:0 0 0 1px var(--teal)}.industry-chain-card.anchor-muted{opacity:.78}.industry-chain-flow{grid-template-columns:repeat(7,minmax(160px,1fr))}
.industry-detail{margin-top:18px;border-top-color:var(--teal)}
.industry-detail-layout{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:22px}
.industry-fact-box{padding:12px 14px;border-left:3px solid var(--accent);background:#fbf6f4;margin:10px 0}.industry-fact-box p{margin:4px 0;color:#455154}
.industry-research-box{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.industry-research-box>div{padding:10px 12px;background:var(--soft);border-left:3px solid var(--teal)}
.industry-company-links{display:flex;flex-wrap:wrap;gap:7px}.industry-company-link{border:1px solid var(--line);background:#fff;padding:7px 10px;cursor:pointer;color:var(--teal);font:inherit;font-weight:700}
.industry-data-state{height:100%;min-height:220px;display:grid;place-items:center;text-align:center;padding:22px;background:repeating-linear-gradient(135deg,#fafbfa,#fafbfa 10px,#f3f5f3 10px,#f3f5f3 20px);color:var(--muted)}.industry-data-state b{display:block;color:var(--ink);font-size:15px}
.industry-data-state p{max-width:100%;overflow-wrap:anywhere}
.industry-evidence-note{font-size:11px;color:var(--muted)}
@media(max-width:1100px){.industry-card-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.industry-detail-layout{grid-template-columns:minmax(0,1fr)}}
@media(max-width:760px){.transmission-tabs{grid-template-columns:1fr}.industry-chain-flow{grid-template-columns:1fr;min-width:0}.industry-card-grid{grid-template-columns:1fr}.industry-research-box{grid-template-columns:1fr}.industry-impact-button{min-height:0}.industry-tier-group-head,.industry-chain-group-head{align-items:flex-start}.industry-gates{grid-template-columns:1fr 1fr}}
@media(max-width:390px){.industry-gates{grid-template-columns:1fr}.industry-tier-tabs{display:grid;grid-template-columns:1fr;width:100%}}
</style>
"""


INDUSTRY_OVERRIDE = r"""
<script>
state.industryMappingId=null;
state.industryTier='CORE_DIRECT';
const industryTierLabels={CORE_DIRECT:'直接影响',SECOND_ORDER:'二阶传导',CONDITIONAL:'条件性影响'};
const industryNodeLabels={
  EVENT_FACT:'事件事实',
  BEHAVIOR_OR_POLICY_CHANGE:'行为或政策变化',
  OBSERVABLE_DRIVER:'可观测驱动',
  INDUSTRY_OPERATING_VARIABLE:'行业经营变量',
  INDUSTRY_REVENUE_OR_COST_VARIABLE:'行业收入或成本变量',
  DIRECTION_ASSESSMENT:'三期限方向',
  PRICE_CONFOUNDER_AND_COUNTEREVIDENCE:'价格、混杂与反证验证'
};
const industryWindowLabels=[['T_MINUS_1','T-1'],['T0','T0'],['D1','D1'],['D3','D3'],['D5','D5'],['D20','D20'],['M3','M3']];

function industryImpact(event,mappingId){
  return (event.industry_impacts||[]).find(function(row){return row.event_industry_mapping_id===mappingId})||null;
}
function selectedIndustryImpact(event){
  const visible=(event.industry_impacts||[]).filter(function(row){return row.impact_tier===state.industryTier});
  return industryImpact(event,state.industryMappingId)||visible[0]||(event.industry_impacts||[])[0]||null;
}
function industryDirectionChips(values){
  values=values||{};
  return '<span class="chips"><span class="chip">即时 '+esc(direction(values.IMMEDIATE))+'</span><span class="chip">短期 '+esc(direction(values.SHORT_TERM))+'</span><span class="chip">中期 '+esc(direction(values.MEDIUM_TERM))+'</span></span>';
}
function industryEvidenceLinks(impact){
  const rows=impact.evidence||[];
  if(!rows.length)return '<span class="chip warn">机制支持证据待补</span>';
  return rows.map(function(row){
    return '<a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">'+esc(row.publisher||row.title||row.evidence_id)+' · '+esc((row.locator||{}).value||'定位待补')+'</a>';
  }).join(' · ');
}
function industryFlowSteps(chain){
  return (chain.nodes||[]).map(function(node,index){
    const evidence=(node.evidence_ids||[]).length?'有引用':'支持证据待补';
    const kind=node.claim_kind==='SOURCE_FACT'?'来源事实':'研究推断';
    return '<div class="transmission-step"><small>'+(index+1)+' · '+esc(industryNodeLabels[node.node_type]||node.node_type)+'</small><b>'+esc(node.statement_zh||'内容待补')+'</b><p>'+kind+' · '+evidence+'</p></div>';
  }).join('');
}
function industryGateSummary(impact){
  const completion=impact.completion||{};
  const gate=completion.gate_statuses||{};
  const coverage=completion.evidence_coverage||{};
  const evidenced=coverage.evidenced_node_count??0;
  const required=coverage.required_node_count??7;
  const companyCount=impact.company_count??(impact.company_links||[]).length;
  return '<div class="industry-gates"><div class="industry-gate"><b>机制证据 '+esc(evidenced)+'/'+esc(required)+'</b>'+esc(status(gate.mechanism_evidence||'DATA_PENDING'))+'</div><div class="industry-gate"><b>驱动数据</b>'+esc(status(gate.driver_data||'DATA_PENDING'))+'</div><div class="industry-gate"><b>行情窗口</b>'+esc(status(gate.market_window||'DATA_PENDING'))+'</div><div class="industry-gate"><b>公司样本 '+esc(companyCount)+' 家</b>'+esc(status(gate.company_sample||'DATA_PENDING'))+'</div></div>';
}
function renderIndustryPaths(event){
  const rows=event.industry_impacts||[];
  const tiers=['CORE_DIRECT','SECOND_ORDER','CONDITIONAL'];
  if(!rows.length)return '<div class="empty">当前事件尚无行业板块链候选。</div>';
  const groups=tiers.map(function(tier){
    const tierRows=rows.filter(function(row){return row.impact_tier===tier});
    if(!tierRows.length)return '';
    const cards=tierRows.map(function(impact){
      const chain=impact.mechanism_chain||{};
      const directions=chain.horizon_directions||{};
      const selected=state.industryMappingId===impact.event_industry_mapping_id?' active':'';
      const anchorMatch=!state.nodeId||impact.anchor_node_id===state.nodeId;
      const anchorClass=anchorMatch?'':' anchor-muted';
      const anchorLabel=state.nodeId?(anchorMatch?'匹配当前时间点':'同事件其他时间点'):'事件主锚点';
      return '<article class="transmission-card industry-chain-card'+selected+anchorClass+'"><header class="transmission-card-head"><div><span class="eyebrow">'+esc(industryTierLabels[impact.impact_tier]||impact.impact_tier)+' · '+esc(impact.classification_edition)+'</span><h3>'+esc(impact.event_title_zh)+' → '+esc(impact.display_name_zh)+'</h3><p>'+esc(impact.behavior_change_zh)+'，经由“'+esc(impact.observable_driver_zh)+'”传导至行业经营与财务变量。</p></div><div class="transmission-actions"><span class="chip">'+esc(anchorLabel)+'</span><span class="chip warn">'+esc(status(impact.review_status))+'</span><button class="link-button" data-industry-detail="'+esc(impact.event_industry_mapping_id)+'">查看行业详情</button></div></header><div class="transmission-flow-wrap"><div class="transmission-flow industry-chain-flow">'+industryFlowSteps(chain)+'</div></div><div class="transmission-card-meta"><div><b>即时 / 短期 / 中期</b>'+esc(direction(directions.IMMEDIATE))+' / '+esc(direction(directions.SHORT_TERM))+' / '+esc(direction(directions.MEDIUM_TERM))+'</div><div><b>生效条件</b>'+esc((chain.conditions_zh||[]).join('；')||'待补')+'</div><div><b>失效条件</b>'+esc((chain.invalidation_conditions_zh||[]).join('；')||'待补')+'</div></div><div class="transmission-evidence"><b>事件锚点证据：</b> '+industryEvidenceLinks(impact)+'<p class="industry-evidence-note">标记为“研究推断”的机制节点仍需单独补充支持证据，不把事件锚点来源扩张为整条链的证明。</p></div></article>';
    }).join('');
    return '<section class="industry-chain-group" data-industry-chain-group="'+tier+'"><div class="industry-chain-group-head"><h3>'+esc(industryTierLabels[tier])+'</h3><span>'+tierRows.length+' 条行业分支 · 全部保持可见</span></div>'+cards+'</section>';
  }).join('');
  return '<div class="transmission-stack">'+groups+'</div>';
}
const baseRenderTransmission=renderTransmission;
renderTransmission=function(event){
  return state.transmissionMode==='industry'?renderIndustryPaths(event):baseRenderTransmission(event);
};

renderIndustries=function(event){
  const rows=event.industry_impacts||[];
  const tiers=['CORE_DIRECT','SECOND_ORDER','CONDITIONAL'];
  const tabs=tiers.map(function(tier){
    const count=rows.filter(function(row){return row.impact_tier===tier}).length;
    return '<button class="industry-tier-button '+(state.industryTier===tier?'active':'')+'" data-industry-tier="'+tier+'">'+industryTierLabels[tier]+' · '+count+'</button>';
  }).join('');
  const groups=tiers.map(function(tier){
    const tierRows=rows.filter(function(row){return row.impact_tier===tier});
    const cards=tierRows.map(function(impact){
      return '<button class="industry-impact-button '+(state.industryMappingId===impact.event_industry_mapping_id?'active':'')+'" data-industry-mapping="'+esc(impact.event_industry_mapping_id)+'" data-tier="'+esc(impact.impact_tier)+'"><span class="eyebrow">'+esc(industryTierLabels[impact.impact_tier])+' · 申万一级 '+esc(impact.sw1_id)+'</span><h3>'+esc(impact.display_name_zh)+'</h3><p>'+esc(impact.observable_driver_zh)+' → '+esc(impact.industry_operating_variable_zh)+'</p>'+industryGateSummary(impact)+'<small>'+esc(status((impact.completion||{}).completion_status))+' · 仍待人工审核</small></button>';
    }).join('');
    return '<section class="industry-tier-group" data-industry-group="'+tier+'"><div class="industry-tier-group-head"><h3>'+esc(industryTierLabels[tier])+'</h3><p>'+tierRows.length+' 个申万一级行业 · 默认全部展开</p></div><div class="industry-card-grid">'+(cards||'<div class="empty">该层级暂无行业候选。</div>')+'</div></section>';
  }).join('');
  return '<div class="industry-tier-tabs" role="tablist" aria-label="行业影响层级">'+tabs+'</div><div class="industry-tier-groups">'+groups+'</div>';
};

const baseCompanyDetailForIndustry=companyDetail;
companyDetail=function(event){
  const impact=industryImpact(event,state.industryMappingId);
  if(impact){
    const companyIds=(impact.company_links||[]).map(function(row){return row.company_id});
    if(!companyIds.length){
      return '<div class="detail"><div class="empty">公司样本待补：当前行业尚未连接公司业务暴露样本，不展示其他行业公司的详情。</div></div>';
    }
  }
  return baseCompanyDetailForIndustry(event);
};

function industryChart(impact){
  const observations=(((impact.market_window||{}).continuous_window||{}).observations)||[];
  const gap=((impact.market_window||{}).data_availability_gap)||{};
  const points=observations.map(function(row,index){
    return {index:index,industry:row.industry_normalized??row.normalized_industry??((row.industry||{}).normalized_value)??null,market:row.market_normalized??row.normalized_market??((row.market||{}).normalized_value)??null};
  });
  const values=points.flatMap(function(row){return [row.industry,row.market]}).filter(function(value){return value!=null&&Number.isFinite(Number(value))});
  if(!values.length)return '<div class="industry-data-state"><div><b>T-20 至 D20 行业走势待补</b><span>'+esc(status(((impact.market_window||{}).window_status)||'DATA_PENDING'))+'</span><p><b>数据库可用性审计</b>'+esc(gap.checked_at||'检查时间待补')+'；当前许可库未发现申万一级与沪深300历史日线。</p><p>缺口代码：'+esc((gap.reason_codes||[]).join('、')||'未登记')+'。缺失值保持为空，不补零，也不使用事件后行情决定行业入选或方向。</p></div></div>';
  let min=Math.min.apply(null,values),max=Math.max.apply(null,values);
  if(max-min<2){min-=1;max+=1}
  const x=function(index){return 55+index*(660/Math.max(1,points.length-1))};
  const y=function(value){return 215-(Number(value)-min)/(max-min)*175};
  const poly=function(key){return points.filter(function(row){return row[key]!=null}).map(function(row){return x(row.index)+','+y(row[key])}).join(' ')};
  return '<svg viewBox="0 0 760 250" role="img" aria-label="行业指数与沪深300 T-20 至 D20 标准化走势"><g stroke="#e1e5e2" stroke-width="1"><line x1="55" y1="40" x2="715" y2="40"/><line x1="55" y1="127" x2="715" y2="127"/><line x1="55" y1="215" x2="715" y2="215"/></g><polyline fill="none" stroke="#a63f35" stroke-width="3" points="'+poly('industry')+'"/><polyline fill="none" stroke="#236b66" stroke-width="3" points="'+poly('market')+'"/><text x="55" y="238" font-size="11" fill="#667175">T-20</text><text x="375" y="238" text-anchor="middle" font-size="11" fill="#667175">T0</text><text x="715" y="238" text-anchor="end" font-size="11" fill="#667175">D20</text><text x="8" y="44" font-size="11" fill="#667175">'+max.toFixed(1)+'</text><text x="8" y="218" font-size="11" fill="#667175">'+min.toFixed(1)+'</text></svg>';
}
function industryWindowTable(impact){
  const fixed=((impact.market_window||{}).fixed_windows)||{};
  return industryWindowLabels.map(function(item){
    const key=item[0],label=item[1],row=fixed[key]||{};
    return '<tr><td>'+label+'</td><td>'+esc(row.actual_date||'数据待补')+'</td><td>'+fmt(row.industry_close??row.industry_value)+'</td><td>'+pct(row.industry_return)+'</td><td>'+fmt(row.market_close??row.market_value)+'</td><td>'+pct(row.market_relative_return)+'</td></tr>';
  }).join('');
}
function industryMechanismDetail(chain){
  return (chain.nodes||[]).map(function(node,index){
    const kind=node.claim_kind==='SOURCE_FACT'?'来源事实':'研究推断';
    return '<div class="mechanism-step"><div class="mechanism-index"><span>'+(index+1)+'</span></div><div class="mechanism-copy"><b>'+esc(industryNodeLabels[node.node_type]||node.node_type)+'</b><p>'+esc(node.statement_zh||'内容待补')+'</p><small>'+kind+' · '+esc((node.evidence_ids||[]).join('、')||'支持证据待补')+'</small></div></div>';
  }).join('');
}
function industryDetail(event){
  const impact=selectedIndustryImpact(event);
  if(!impact)return '<div class="detail industry-detail"><div class="empty">行业影响详情待生成。</div></div>';
  state.industryMappingId=impact.event_industry_mapping_id;
  const chain=impact.mechanism_chain||{};
  const driver=((impact.driver||{}).primary_driver)||{};
  const companies=impact.company_links||[];
  const evidence=(impact.evidence||[]).map(function(row){
    return '<div class="evidence-item"><b>'+esc(row.title||row.evidence_id)+'</b><p>'+esc(row.original_quote||row.evidence_summary||'原文引文待补')+'</p><small>'+esc(row.publisher)+' · '+esc(row.published_at)+' · '+esc(row.availability_scope)+' · '+esc((row.locator||{}).value||'定位待补')+'</small><br><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener noreferrer">打开官方证据</a></div>';
  }).join('')||'<div class="empty">事件锚点证据待补。</div>';
  const companyLinks=companies.map(function(row){
    return '<button class="industry-company-link" data-industry-company="'+esc(row.company_id)+'">'+esc(row.company_name)+' · '+esc(row.company_code)+'</button>';
  }).join('')||'<div class="empty">公司样本待补：行业候选保留，但尚未连接到公司业务暴露样本。</div>';
  const labels=(impact.segment_labels_zh||[]).map(function(label){return '<span class="chip">'+esc(label)+'</span>'}).join('');
  const counter=(chain.counterevidence_zh||impact.counterevidence_zh||[]).join('；')||'反证待补';
  return '<div class="detail industry-detail"><div class="detail-head"><div><span class="eyebrow">'+esc(impact.event_industry_mapping_id)+' · '+esc(industryTierLabels[impact.impact_tier])+'</span><h3>行业影响详情 · '+esc(impact.display_name_zh)+'</h3><p>'+esc(impact.event_title_zh)+' → '+esc(impact.behavior_change_zh)+' → '+esc(impact.observable_driver_zh)+'</p></div><span class="chip warn">'+esc(status(impact.review_status))+'</span></div><div class="chips"><span class="chip">'+esc(impact.classification_edition)+' · '+esc(impact.sw1_id)+'</span>'+labels+'<span class="chip warn">'+esc((impact.completion||{}).completion_status||'OPEN')+'</span></div><div class="industry-fact-box"><b>已验证事件锚点</b><p>'+esc(impact.anchor_fact)+'</p><small>发生：'+esc(impact.anchor_occurred_at)+' · 首次公开：'+esc(impact.anchor_first_public_at)+' · '+industryEvidenceLinks(impact)+'</small></div><h4>七步行业机制链</h4><div class="mechanism-flow">'+industryMechanismDetail(chain)+'</div><div class="industry-research-box"><div><b>三期限方向</b>'+industryDirectionChips(chain.horizon_directions)+'</div><div><b>生效条件</b><br>'+esc((chain.conditions_zh||[]).join('；')||'待补')+'</div><div><b>失效条件</b><br>'+esc((chain.invalidation_conditions_zh||[]).join('；')||'待补')+'</div></div><div class="industry-detail-layout"><div><h4>T-20 至 D20 行业与大盘折线图</h4><div class="legend"><span><i style="background:#a63f35"></i>'+esc(impact.display_name_zh)+'（T-1=100）</span><span><i style="background:#236b66"></i>沪深300（T-1=100）</span></div><div class="chart-wrap">'+industryChart(impact)+'</div></div><div><h4>驱动变量</h4><p><b>'+esc(driver.name_zh||impact.observable_driver_zh)+'</b></p><p>单位：'+esc(driver.unit_zh||impact.driver_unit_zh||'待补')+'；频率：'+esc(driver.frequency||'UNKNOWN')+'；数据状态：'+esc(status(driver.source_status||'DATA_PENDING'))+'</p><p>'+esc(driver.selection_basis_zh||'驱动变量按事件前机制预先指定。')+'</p><h4>经营与财务变量</h4><p><b>经营：</b>'+esc(impact.industry_operating_variable_zh)+'</p><p><b>收入/成本：</b>'+esc(impact.industry_financial_variable_zh)+'</p></div></div><h4>固定行情窗口</h4><div class="table-wrap"><table class="market-table"><thead><tr><th>窗口</th><th>实际交易日</th><th>行业指数</th><th>行业收益</th><th>沪深300</th><th>相对收益</th></tr></thead><tbody>'+industryWindowTable(impact)+'</tbody></table></div><h4>证据来源</h4><div class="evidence-list">'+evidence+'</div><h4>混杂、竞争解释与反证</h4><div class="notice">'+esc(counter)+'。价格仅用于验证，不用于选择行业或生成方向。</div><h4>关联公司样本</h4><div class="industry-company-links">'+companyLinks+'</div><details class="raw-details"><summary>技术详情与完成门禁</summary><div class="raw-details-body"><p><code>'+esc(impact.event_industry_mapping_id)+'</code></p><p>主驱动：<code>'+esc(driver.driver_series_id||'DATA_PENDING')+'</code></p><p>行业窗口：<code>'+esc(((impact.market_window||{}).industry_market_window_id)||'DATA_PENDING')+'</code></p><p>阻塞项：'+esc(((impact.completion||{}).blockers||[]).join('、')||'无')+'</p><p>formal_ready=false · sha_gate=DEFERRED · review_status='+esc(impact.review_status)+'</p></div></details></div>';
}

const baseRenderMainForIndustry=renderMain;
renderMain=function(){
  const event=currentEvent();
  const impacts=event.industry_impacts||[];
  if(!impacts.some(function(row){return row.event_industry_mapping_id===state.industryMappingId})){
    const first=impacts.find(function(row){return row.impact_tier===state.industryTier})||impacts[0];
    state.industryMappingId=first?first.event_industry_mapping_id:null;
    state.industryId=first?first.sw1_id:null;
  }
  const activeImpact=industryImpact(event,state.industryMappingId);
  const activeCompanyIds=activeImpact?(activeImpact.company_links||[]).map(function(row){return row.company_id}):[];
  if(activeImpact){
    if(activeCompanyIds.length&&!activeCompanyIds.includes(state.companyId))state.companyId=activeCompanyIds[0];
    if(!activeCompanyIds.length)state.companyId='__NO_INDUSTRY_COMPANY__';
  }
  baseRenderMainForIndustry();
  const tabs=document.querySelector('.transmission-tabs');
  if(tabs&&!tabs.querySelector('[data-transmission-mode="industry"]')){
    const macro=tabs.querySelector('[data-transmission-mode="macro"]');
    if(macro)macro.insertAdjacentHTML('beforebegin','<button class="transmission-tab '+(state.transmissionMode==='industry'?'active':'')+'" data-transmission-mode="industry" role="tab" aria-selected="'+(state.transmissionMode==='industry')+'">行业板块链</button>');
  }
  const industryHeading=Array.from(document.querySelectorAll('.section-head h2')).find(function(node){return node.textContent.trim()==='行业影响'});
  const section=industryHeading?industryHeading.closest('.section'):null;
  if(section)section.insertAdjacentHTML('beforeend',industryDetail(event));
  document.querySelectorAll('[data-transmission-mode]').forEach(function(button){button.onclick=function(){state.transmissionMode=button.dataset.transmissionMode;renderMain()}});
  document.querySelectorAll('[data-industry-tier]').forEach(function(button){button.onclick=function(){
    state.industryTier=button.dataset.industryTier;
    renderMain();
    requestAnimationFrame(function(){
      const group=document.querySelector('[data-industry-group="'+state.industryTier+'"]');
      if(group)group.scrollIntoView({behavior:'smooth',block:'start'});
    });
  }});
  document.querySelectorAll('[data-industry-mapping],[data-industry-detail]').forEach(function(button){button.onclick=function(){
    const mappingId=button.dataset.industryMapping||button.dataset.industryDetail;
    const impact=industryImpact(event,mappingId);
    state.industryMappingId=mappingId;
    state.industryTier=impact?impact.impact_tier:state.industryTier;
    state.industryId=impact?impact.sw1_id:null;
    if(button.dataset.industryDetail)state.transmissionMode='industry';
    state.companyId=null;
    renderMain();
    requestAnimationFrame(function(){const detail=document.querySelector('.industry-detail');if(detail)detail.scrollIntoView({behavior:'smooth',block:'start'})});
  }});
  document.querySelectorAll('[data-industry-company]').forEach(function(button){button.onclick=function(){
    state.companyId=button.dataset.industryCompany;
    renderMain();
    requestAnimationFrame(function(){const grid=document.querySelector('.company-grid');if(grid)grid.scrollIntoView({behavior:'smooth',block:'start'})});
  }});
};
renderMain();
</script>
"""


INDUSTRY_CLOSURE_OVERRIDE = r"""
<style>
.mechanism-class{display:inline-flex;margin-top:6px;padding:2px 7px;border:1px solid var(--line);font-size:10px;font-weight:700}
.mechanism-class.source{color:#176454;background:#eaf4f2}.mechanism-class.calculated{color:#1f5687;background:#edf5fb}.mechanism-class.inference{color:#596467;background:#f0f2f1}
.node-evidence-list{display:grid;gap:6px;margin-top:8px}.node-evidence{padding:8px 10px;background:#fff;border-left:3px solid var(--teal)}.node-evidence p{margin:3px 0}.node-evidence small{display:block;color:var(--muted)}
.inference-boundary{margin-top:7px;padding:8px 10px;background:#f0f2f1;color:#4d595c;font-size:11px}
.industry-chart-controls{display:flex;gap:5px;margin:7px 0}.industry-chart-controls button{border:1px solid var(--line);background:#fff;padding:5px 9px;cursor:pointer}.industry-chart-controls button.active{background:var(--ink);color:#fff}
.industry-chart-view[hidden]{display:none}.industry-concurrence-list{display:grid;gap:8px}.industry-concurrence{padding:12px 14px;border-left:4px solid var(--gold);background:#fffaf0}.industry-concurrence.dominant{border-left-color:var(--accent)}
.industry-concurrence h5{margin:0 0 5px;font-size:14px}.industry-concurrence p{margin:5px 0}.industry-concurrence dl{display:grid;grid-template-columns:86px minmax(0,1fr);gap:4px 10px;margin:8px 0}.industry-concurrence dt{font-weight:700}.industry-concurrence dd{margin:0}
.driver-observations{display:grid;gap:5px;margin-top:8px}.driver-observation{display:flex;justify-content:space-between;gap:10px;padding:6px 8px;background:var(--soft);font-size:11px}
.formula-details{margin-top:3px}.formula-details summary{cursor:pointer;color:var(--teal);font-size:11px}
@media(max-width:760px){.industry-concurrence dl{grid-template-columns:1fr}.driver-observation{display:block}}
</style>
<script>
function closureLocator(row){
  const value=row&&row.locator;
  if(value&&typeof value==='object')return value.value||value.label||'定位待补';
  return value||'定位待补';
}
function closureStatementClass(value){
  if(value==='SOURCE_FACT')return {label:'来源事实',className:'source'};
  if(value==='CALCULATED_FACT')return {label:'计算事实',className:'calculated'};
  return {label:'研究推断',className:'inference'};
}
industryEvidenceLinks=function(impact){
  const rows=impact.evidence||[];
  if(!rows.length)return '<span class="chip warn">机制支持证据待核验</span>';
  return rows.map(function(row){
    return '<a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener">'+esc(row.publisher||row.title||row.evidence_id)+' · 查看原文</a>';
  }).join(' · ');
};
industryFlowSteps=function(chain){
  return (chain.nodes||[]).map(function(node,index){
    const kind=closureStatementClass(node.statement_class);
    const evidenceCount=(node.evidence||[]).length;
    const evidenceText=node.statement_class==='RESEARCH_INFERENCE'?'明确条件与失效边界':(evidenceCount?'已连接 '+evidenceCount+' 条原文':'证据待核验');
    return '<div class="transmission-step"><small>'+(index+1)+' · '+esc(industryNodeLabels[node.node_type]||node.node_type)+'</small><b>'+esc(node.statement_zh||'内容待补')+'</b><span class="mechanism-class '+kind.className+'">'+kind.label+'</span><p>'+evidenceText+'</p></div>';
  }).join('');
};
function closureEvidenceCard(row){
  return '<div class="node-evidence"><b>'+esc(row.title||row.evidence_id)+'</b><p>“'+esc(row.original_quote||'原文引文待核验')+'”</p><small>'+esc(row.publisher)+' · '+esc(row.published_at)+' · '+esc(row.availability_scope)+' · '+esc(closureLocator(row))+'</small><a class="evidence-link" href="'+esc(row.source_url)+'" target="_blank" rel="noopener">查看原文</a></div>';
}
industryMechanismDetail=function(chain){
  return (chain.nodes||[]).map(function(node,index){
    const kind=closureStatementClass(node.statement_class);
    const evidence=(node.evidence||[]).map(closureEvidenceCard).join('');
    const pending=node.statement_class==='SOURCE_FACT'&&!evidence?'<div class="empty">证据待核验：'+esc((node.missing_evidence_ids||[]).join('、')||node.evidence_status||'EVIDENCE_PENDING')+'</div>':'';
    const inference=node.statement_class==='RESEARCH_INFERENCE'?'<div class="inference-boundary"><b>推断前提：</b>'+esc((node.premise_node_ids||[]).join('、'))+'<br><b>生效条件：</b>'+esc(node.condition_zh||'待补')+'<br><b>失效条件：</b>'+esc(node.invalidation_zh||'待补')+'</div>':'';
    return '<div class="mechanism-step"><div class="mechanism-index"><span>'+(index+1)+'</span></div><div class="mechanism-copy"><b>'+esc(industryNodeLabels[node.node_type]||node.node_type)+'</b><p>'+esc(node.statement_zh||'内容待补')+'</p><span class="mechanism-class '+kind.className+'">'+kind.label+'</span><div class="node-evidence-list">'+evidence+pending+'</div>'+inference+'</div></div>';
  }).join('');
};
function setIndustryChartMode(button,mode){
  const root=button.closest('.industry-chart');
  if(!root)return;
  root.querySelectorAll('[data-chart-mode]').forEach(function(item){item.classList.toggle('active',item.dataset.chartMode===mode)});
  root.querySelectorAll('[data-chart-view]').forEach(function(item){item.hidden=item.dataset.chartView!==mode});
}
function closureChartSvg(points,driverPoints,mode,t0Index){
  const keyIndustry=mode==='raw'?'industry_value':'industry_normalized';
  const keyMarket=mode==='raw'?'market_value':'market_normalized';
  const values=points.flatMap(function(row){return [row[keyIndustry],row[keyMarket]]}).filter(function(value){return value!=null&&Number.isFinite(Number(value))});
  if(!values.length)return '';
  let min=Math.min.apply(null,values),max=Math.max.apply(null,values);
  if(max===min){min-=1;max+=1}
  const x=function(index){return 58+index*(650/Math.max(1,points.length-1))};
  const y=function(value){return 210-(Number(value)-min)/(max-min)*165};
  const poly=function(key){return points.map(function(row,index){return row[key]==null?null:x(index)+','+y(row[key])}).filter(Boolean).join(' ')};
  const numericDriver=driverPoints.filter(function(row){return row.value!=null&&Number.isFinite(Number(row.value))});
  let driverMin=numericDriver.length?Math.min.apply(null,numericDriver.map(function(row){return Number(row.value)})):0;
  let driverMax=numericDriver.length?Math.max.apply(null,numericDriver.map(function(row){return Number(row.value)})):1;
  if(driverMin===driverMax){driverMin-=1;driverMax+=1}
  const driverY=function(value){return 210-(Number(value)-driverMin)/(driverMax-driverMin)*165};
  const circles=numericDriver.map(function(row){return '<circle cx="'+x(row.index)+'" cy="'+driverY(row.value)+'" r="4" fill="#9a721e"><title>'+esc(row.metric_code)+' '+esc(row.value)+' '+esc(row.unit)+'</title></circle>'}).join('');
  const t0x=x(Math.max(0,t0Index));
  return '<svg viewBox="0 0 760 250" role="img" aria-label="行业、沪深300与主驱动走势"><g stroke="#e1e5e2"><line x1="58" y1="45" x2="708" y2="45"/><line x1="58" y1="127" x2="708" y2="127"/><line x1="58" y1="210" x2="708" y2="210"/></g><line x1="'+t0x+'" y1="35" x2="'+t0x+'" y2="218" stroke="#667175" stroke-dasharray="4 4"/><polyline fill="none" stroke="#a63f35" stroke-width="3" points="'+poly(keyIndustry)+'"/><polyline fill="none" stroke="#236b66" stroke-width="3" points="'+poly(keyMarket)+'"/>'+circles+'<text x="'+t0x+'" y="232" text-anchor="middle" font-size="11" fill="#667175">T0</text><text x="58" y="242" font-size="10" fill="#667175">'+esc(points[0].actual_date||'T-20')+'</text><text x="708" y="242" text-anchor="end" font-size="10" fill="#667175">'+esc(points[points.length-1].actual_date||'D20')+'</text><text x="6" y="48" font-size="10" fill="#667175">'+max.toFixed(2)+'</text><text x="6" y="213" font-size="10" fill="#667175">'+min.toFixed(2)+'</text><text x="754" y="48" text-anchor="end" font-size="10" fill="#9a721e">'+driverMax.toFixed(2)+'</text><text x="754" y="213" text-anchor="end" font-size="10" fill="#9a721e">'+driverMin.toFixed(2)+'</text></svg>';
}
industryChart=function(impact){
  const marketWindow=impact.market_window||{};
  const continuous=marketWindow.continuous_window||[];
  const points=Array.isArray(continuous)?continuous:(continuous.observations||[]);
  const driver=impact.driver||{};
  const driverRows=driver.observations||[];
  if(!points.length){
    return '<div class="industry-data-state"><div><b>T-20 至 D20 行业走势待补</b><span>'+esc(status(marketWindow.window_status||'DATA_PENDING'))+'</span><p>缺口代码：'+esc(marketWindow.pending_reason||'MARKET_SERIES_NOT_AVAILABLE')+'。缺失值保持为空，不补零。</p></div></div>';
  }
  const t0Date=((marketWindow.t0_alignment||{}).T0);
  const t0Index=Math.max(0,points.findIndex(function(row){return row.actual_date===t0Date}));
  const driverPoints=driverRows.map(function(row){
    const observed=row.observed_at||row.period;
    let index=points.findIndex(function(point){return point.actual_date>=observed});
    if(index<0)index=points.length-1;
    return {...row,index:index};
  });
  return '<div class="industry-chart" data-mode="normalized"><div class="industry-chart-controls"><button class="active" data-chart-mode="normalized" onclick="setIndustryChartMode(this,\'normalized\')">归一化值</button><button data-chart-mode="raw" onclick="setIndustryChartMode(this,\'raw\')">原始值</button></div><div class="industry-chart-view" data-chart-view="normalized">'+closureChartSvg(points,driverPoints,'normalized',t0Index)+'</div><div class="industry-chart-view" data-chart-view="raw" hidden>'+closureChartSvg(points,driverPoints,'raw',t0Index)+'</div></div>';
};
industryWindowTable=function(impact){
  const fixed=((impact.market_window||{}).fixed_windows)||{};
  return industryWindowLabels.map(function(item){
    const key=item[0],label=item[1],row=fixed[key]||{};
    const inputs=row.formula_inputs||{};
    const formula=row.formula||'待补';
    return '<tr><td>'+label+'</td><td>'+esc(row.actual_date||'数据待补')+'</td><td>'+fmt(row.industry_value)+'</td><td>'+pct(row.industry_return)+'</td><td>'+fmt(row.market_value)+'</td><td>'+pct(row.market_return)+'</td><td>'+pct(row.market_relative_return)+'<details class="formula-details"><summary>公式输入</summary><code>'+esc(formula)+'</code><br>'+esc(JSON.stringify(inputs))+'</details></td></tr>';
  }).join('');
};
function closureDriverHtml(driver){
  const observations=(driver.observations||[]).map(function(row){
    const value=row.value==null?'DATA_PENDING':fmt(row.value)+' '+esc(row.unit);
    return '<div class="driver-observation"><span>'+esc(row.observed_at)+' · '+esc(row.metric_code)+'</span><b>'+value+'</b></div>';
  }).join('')||'<div class="empty">驱动观测待补。</div>';
  const selectionBasisLabels={
    PRE_REGISTERED_OPERATING_DRIVER_NOT_SELECTED_BY_PRICE:'经营驱动在事件前预先登记，未按事后价格表现选择'
  };
  const selectionBasis=driver.selection_basis_zh||selectionBasisLabels[driver.selection_basis]||driver.selection_basis||'事件前机制预先指定，未使用事后价格选样。';
  return '<h4>主驱动（右轴）</h4><p><b>'+esc(driver.driver_name_zh||'驱动待补')+'</b></p><p>单位：'+esc(driver.unit_zh||'待补')+'；频率：'+esc(driver.frequency||'UNKNOWN')+'；状态：'+esc(status(driver.source_status||'DATA_PENDING'))+'</p><p>'+esc(selectionBasis)+'</p><div class="driver-observations">'+observations+'</div>';
}
function closureConfounderHtml(chain){
  const rows=chain.confounders||[];
  if(!rows.length)return '<div class="empty">混杂、竞争解释与反证待补。</div>';
  return '<div class="industry-concurrence-list">'+rows.map(function(row){
    const severity=(row.severity||'UNRESOLVED').toLowerCase();
    const counters=(row.counterevidence_zh||[]).map(function(text){return '<li>'+esc(text)+'</li>'}).join('');
    const tests=(row.distinguishing_tests_zh||[]).map(function(text){return '<li>'+esc(text)+'</li>'}).join('');
    const sources=(row.evidence||[]).map(closureEvidenceCard).join('');
    const evidence=sources||'<div class="empty">混杂证据待核验：'+esc(row.missing_evidence_reason||'CONFOUNDER_SOURCE_NOT_VERIFIED')+'</div>';
    const kind=closureStatementClass(row.statement_class||'RESEARCH_INFERENCE');
    return '<article class="industry-concurrence '+severity+'"><h5>'+esc(row.event_zh)+' <span class="chip warn">'+esc(row.severity)+'</span> <span class="mechanism-class '+kind.className+'">'+kind.label+'</span> '+(row.challenge_set_only?'<span class="chip">挑战集</span>':'')+'</h5><p><b>混杂分析：</b>'+esc(row.analysis_zh||row.alternative_explanation_zh)+'</p><dl><dt>影响窗口</dt><dd>'+esc((row.affected_windows||[]).join('、'))+'</dd><dt>机制重叠</dt><dd>'+esc(row.mechanism_overlap)+'</dd><dt>竞争解释</dt><dd>'+esc(row.alternative_explanation_zh)+'</dd><dt>归因边界</dt><dd>'+esc(row.attribution_limit_zh)+'</dd></dl><b>区分检验</b><ul>'+tests+'</ul><b>反证</b><ul>'+counters+'</ul><div class="node-evidence-list">'+evidence+'</div></article>';
  }).join('')+'</div>';
}
industryDetail=function(event){
  const impact=selectedIndustryImpact(event);
  if(!impact)return '<div class="detail industry-detail"><div class="empty">行业影响详情待生成。</div></div>';
  state.industryMappingId=impact.event_industry_mapping_id;
  const chain=impact.mechanism_chain||{};
  const driver=impact.driver||{};
  const companies=impact.company_links||[];
  const evidence=(impact.evidence||[]).map(closureEvidenceCard).join('')||'<div class="empty">逐节点证据待核验。</div>';
  const companyLinks=companies.map(function(row){return '<button class="industry-company-link" data-industry-company="'+esc(row.company_id)+'">'+esc(row.company_name)+' · '+esc(row.company_code)+'</button>'}).join('')||'<div class="empty">行业机制已建立，当前尚未配置公司样本。</div>';
  const labels=(impact.segment_labels_zh||[]).map(function(label){return '<span class="chip">'+esc(label)+'</span>'}).join('');
  return '<div class="detail industry-detail"><div class="detail-head"><div><span class="eyebrow">'+esc(impact.event_industry_mapping_id)+' · '+esc(industryTierLabels[impact.impact_tier])+'</span><h3>行业影响详情 · '+esc(impact.display_name_zh)+'</h3><p>'+esc(impact.event_title_zh)+' → '+esc(impact.behavior_change_zh)+' → '+esc(impact.observable_driver_zh)+'</p></div><span class="chip warn">'+esc(status(impact.review_status))+'</span></div><div class="chips"><span class="chip">'+esc(impact.classification_edition)+' · '+esc(impact.sw1_id)+'</span>'+labels+'<span class="chip warn">'+esc((impact.completion||{}).completion_status||'OPEN')+'</span></div><div class="industry-fact-box"><b>事件锚点</b><p>'+esc(impact.anchor_fact||impact.event_title_zh)+'</p><small>发生：'+esc(impact.anchor_occurred_at||'待核验')+' · 首次公开：'+esc(impact.anchor_first_public_at||'待核验')+'</small></div><h4>七步行业机制链</h4><div class="mechanism-flow">'+industryMechanismDetail(chain)+'</div><div class="industry-research-box"><div><b>三期限方向</b>'+industryDirectionChips(chain.horizon_directions)+'</div><div><b>生效条件</b><br>'+esc((chain.conditions_zh||[]).join('；')||'待补')+'</div><div><b>失效条件</b><br>'+esc((chain.invalidation_conditions_zh||[]).join('；')||'待补')+'</div></div><div class="industry-detail-layout"><div><h4>T-20 至 D20 行业、沪深300与驱动对比</h4><div class="legend"><span><i style="background:#a63f35"></i>'+esc(impact.display_name_zh)+'</span><span><i style="background:#236b66"></i>沪深300</span><span><i style="background:#9a721e"></i>主驱动（右轴）</span></div><div class="chart-wrap">'+industryChart(impact)+'</div></div><div>'+closureDriverHtml(driver)+'</div></div><h4>固定行情窗口</h4><div class="table-wrap"><table class="market-table"><thead><tr><th>窗口</th><th>实际交易日</th><th>行业指数</th><th>行业收益</th><th>沪深300</th><th>大盘收益</th><th>相对收益</th></tr></thead><tbody>'+industryWindowTable(impact)+'</tbody></table></div><h4>证据来源</h4><div class="evidence-list">'+evidence+'</div><h4>混杂、竞争解释与反证</h4>'+closureConfounderHtml(chain)+'<div class="notice">价格仅用于验证，不用于选择行业或生成方向；MATERIAL、DOMINANT 与 UNRESOLVED 仅进入挑战集。</div><h4>关联公司样本</h4><div class="industry-company-links">'+companyLinks+'</div><details class="raw-details"><summary>技术详情与完成门禁</summary><div class="raw-details-body"><p><code>'+esc(impact.event_industry_mapping_id)+'</code></p><p>主驱动：<code>'+esc(driver.driver_series_id||'DATA_PENDING')+'</code></p><p>阻塞项：'+esc(((impact.completion||{}).blockers||[]).join('、')||'无')+'</p><p>formal_ready=false · sha_gate=DEFERRED · review_status='+esc(impact.review_status)+'</p></div></details></div>';
};
renderMain();
</script>
"""

def render_workbench(bundle: Mapping[str, Any]) -> str:
    html = _base.render_workbench(bundle)
    version_payload = json.dumps(
        bundle.get("summary", {}).get("industry_overlay_versions", []),
        ensure_ascii=False,
    ).replace("<", "\u003c")
    html = html.replace(
        "</head>",
        '<script type="application/json" id="industry-overlay-versions">'
        + version_payload
        + "</script></head>",
    )
    html = html.replace(
        "公告标题检索未发现高风险候选，正文检索与公司级反证仍待完成。当前等级：",
        "混杂证据按映射级门禁展示。当前等级：",
    )
    html = html.replace(
        "当前仅登记公告标题级候选；正文未审项目一律为 UNRESOLVED，仅进入挑战集，不支持干净因果归因。公司级反证检索仍待完成。",
        "以下论证来自官方公告正文、负向检索审计、六窗口交易状态和公司级反证；所有结论仍待人工审核。",
    )
    html = html.replace("</head>", INDUSTRY_STYLE + "</head>")
    return html.replace(
        "</body>",
        CONFOUNDER_OVERRIDE + INDUSTRY_OVERRIDE + INDUSTRY_CLOSURE_OVERRIDE + "</body>",
    )


def write_ui(
    root: Path,
    output_root: Path,
    *,
    candidate_root: Path | None = None,
    industry_root: Path | None = None,
    industry_overlay_root: Path | None = None,
) -> dict[str, Any]:
    bundle = build_ui_bundle(
        root,
        candidate_root=candidate_root,
        industry_root=industry_root,
        industry_overlay_root=industry_overlay_root,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "ui_data_bundle.js").write_text(
        "window.FINGOOSE_COMPANY_IMPACT_V2="
        + json.dumps(
            bundle,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + ";\n",
        encoding="utf-8",
    )
    (output_root / "index.html").write_text(
        render_workbench(bundle),
        encoding="utf-8",
    )
    return bundle["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--industry", type=Path, required=True)
    parser.add_argument("--industry-overlay", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    def resolve(value: Path | None) -> Path | None:
        if value is None:
            return None
        return value if value.is_absolute() else root / value

    summary = write_ui(
        root,
        resolve(args.output),
        candidate_root=resolve(args.candidate),
        industry_root=resolve(args.industry),
        industry_overlay_root=resolve(args.industry_overlay),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
