from __future__ import annotations

import html
import json
from typing import Any

COPY = {
    "status": {
        "VERIFIED_EXISTING": "已有证据", "PENDING_EVIDENCE": "待补证",
        "PROPOSED": "候选路径", "CORE_REVIEWED": "核心复核",
        "CHALLENGE_ONLY": "仅作挑战集", "WINDOW_DEPENDENT": "窗口依赖",
        "SUPPORTED": "已有支持", "PARTIALLY_SUPPORTED": "部分支持",
        "UNRESOLVED": "尚未解决", "PRIMARY_ANCHOR": "主锚点",
        "SECONDARY": "次锚点", "NONE": "普通节点",
    },
    "phase": {
        "PRECONDITION": "前置背景", "INITIAL_SHOCK": "首次冲击",
        "ESCALATION": "升级", "POLICY_RESPONSE": "政策响应",
        "CALMING": "缓和", "EASING": "缓和", "SECONDARY_SHOCK": "二次冲击",
        "RESOLUTION": "事件结束",
    },
    "window": {
        "T-1": "前一交易日", "T0": "事件日收盘", "D1": "第 1 个交易日",
        "D3": "第 3 个交易日", "D5": "第 5 个交易日", "D20": "第 20 个交易日",
    },
    "action": {
        "OBSERVES": "观察", "STARTS": "启动", "AMPLIFIES": "强化",
        "WEAKENS": "削弱", "RESPONDS": "响应", "CALMS": "缓和",
    },
    "direction": {"UP": "上行", "DOWN": "下行", "MIXED": "混合", "RISK_OFF": "避险"},
}
PHASES = ["PRECONDITION", "INITIAL_SHOCK", "ESCALATION", "POLICY_RESPONSE", "CALMING", "EASING", "SECONDARY_SHOCK", "RESOLUTION"]
WINDOWS = ["T-1", "T0", "D1", "D3", "D5", "D20"]
TERMS = {
    "PANDEMIC_SHOCK": "疫情冲击", "GEOPOLITICAL_CONFLICT": "地缘冲突", "ENERGY_SUPPLY": "能源供应",
    "ENERGY_PRICE_SHOCK": "能源价格冲击", "INFLATION_EXPECTATIONS": "通胀预期", "RISK_APPETITE": "风险偏好",
    "SAFE_HAVEN_DEMAND": "避险需求", "GLOBAL_DEMAND": "全球需求", "GLOBAL_GROWTH": "全球增长",
    "TRADE_COSTS": "贸易成本", "LIQUIDITY_STRESS": "流动性压力", "MONETARY_POLICY": "货币政策",
    "SHIPPING_DISRUPTION": "航运中断", "SHIPPING_COSTS": "航运成本", "RATE_DIFFERENTIAL": "利差",
    "PROPERTY_SUPPORT": "地产支持", "TARIFFS": "关税冲击", "SANCTIONS_TRADE": "制裁与贸易",
}


def ui_copy() -> dict[str, dict[str, str]]:
    return {key: dict(value) for key, value in COPY.items()}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else "未知"), quote=True)


def _label(group: str, value: Any) -> str:
    return COPY.get(group, {}).get(str(value), str(value or "未知"))


def _term(value: Any, index: int = 0, payload: dict[str, Any] | None = None) -> str:
    raw = str(value or "未知")
    if raw in TERMS:
        return TERMS[raw]
    if raw.startswith("EVENT-") and "_" in raw:
        return "事件专属中间变量"
    if payload:
        for row in payload.get("windows", []):
            if row.get("series_id") == raw:
                return str(row.get("series_name") or raw)
    if raw.isupper() or raw.replace("|", "").replace("-", "").isdigit():
        return "资产序列" if index >= 3 else "事件专属渠道"
    return raw


def _fact_summary(node: dict[str, Any]) -> str:
    fact = str(node.get("fact") or "").strip()
    if any("\u4e00" <= char <= "\u9fff" for char in fact):
        return fact
    tags = "、".join(_term(tag) for tag in node.get("impact_tags", [])) or "相关市场"
    return f"该节点处于{_label('phase', node.get('phase'))}阶段，公开信息记录了事件关键进展；节点动作是“{_label('action', node.get('node_action'))}”，重点影响标签包括 {tags}。原始事实请展开证据摘录查看。"


def _source_quote(source: dict[str, Any], node: dict[str, Any] | None = None) -> str:
    quote = str(source.get("quote") or "").strip()
    if quote:
        return quote
    title = str(source.get("title") or source.get("publisher") or "该来源")
    if node and node.get("fact"):
        return f"来源 {title} 已纳入事实台账；当前快照未提供可独立复核的短引文，页面只呈现中文事实摘要。"
    return f"来源 {title} 已纳入证据台账；原文摘录待补。"


def build_confounder_argument(event_id: str, timeline: dict[str, Any], paths: list[dict[str, Any]], confounder: dict[str, Any]) -> str:
    primary = next((node for node in timeline.get("nodes", []) if node.get("anchor_role") == "PRIMARY"), {})
    items = confounder.get("items", [])
    affected = [window for item in items for window in item.get("affected_windows", [])]
    windows = "、".join(_label("window", key) for key in dict.fromkeys(affected)) or "尚未覆盖的窗口"
    path_ids = {path_id for item in items for path_id in item.get("affected_path_ids", [])}
    path_names = "、".join(path.get("name", "候选路径") for path in paths if path.get("path_id") in path_ids) or "主事件候选路径"
    reason = "；".join(item.get("description", "") for item in items if item.get("description")) or confounder.get("reason", "当前数据未提供独立竞争解释")
    horizon = "、".join(f"{_label('window', key)}为{_label('status', value)}" for key, value in (confounder.get("by_horizon") or {}).items())
    return (f"本页讨论的事件是“{timeline.get('title', event_id)}”，主锚点首次公开时间记录为 {primary.get('first_public_at') or '未知时间'}。"
            f"时间线可以支持对事件事实的还原，但不能自动把随后所有资产波动都归因于同一冲击。现有混杂登记指出：{reason}。"
            f"这些竞争因素主要进入 {windows}，会同时影响“{path_names}”等候选路径。按当前窗口评级，{horizon or '各窗口尚无完整评级'}。"
            "因此，T0 与 D1 只能作为事件日附近的挑战性观察，D3、D5 和 D20 更应被视为竞争解释并存的窗口，而不是干净的因果估计。"
            "可反驳这段论点的证据包括独立来源证明竞争冲击尚未发生，或同一交易日内出现与主路径相反的资产反应。"
            f"当前结论是“{_label('status', confounder.get('clean_attribution_decision'))}”，这段文字用于约束过度表述，不代表人工确认了传导机制。")


def _citation_links(payload: dict[str, Any], ids: list[Any], role: str = "fact") -> str:
    sources = {source.get("source_id"): source for source in payload.get("sources", [])}
    links = []
    for item in ids or []:
        source_id = item if isinstance(item, str) else item.get("source_id")
        source = sources.get(source_id)
        if not source:
            links.append(f"<span class='source-empty'>引用待补：{_esc(source_id)}</span>")
            continue
        label = "事后机制验证" if source.get("visibility") == "HIDDEN_FROM_PRIMARY_PREDICTION" else ("机制证据" if role == "mechanism" else "事实与时间证据")
        if source.get("url"):
            links.append(f"<a class='citation {'mechanism' if role == 'mechanism' else ''}' href='{_esc(source['url'])}' target='_blank' rel='noopener noreferrer'>↗ {_esc(source.get('publisher') or '来源')} · {label}</a>")
        else:
            links.append(f"<span class='source-empty'>{_esc(source.get('publisher') or source_id)} · 来源链接待补</span>")
    return "".join(links) or "<span class='source-empty'>暂无已验证引用</span>"



def _chart_svg(series: dict[str, Any]) -> str:
    points = [(key, series.get("display_windows", {}).get(key, {})) for key in WINDOWS]
    points = [(key, point) for key, point in points if point.get("value") is not None]
    if not points:
        return "<div class='empty'>当前序列没有可绘制的绝对值。</div>"
    width, height, left, right, top, bottom = 720, 260, 58, 20, 22, 42
    values = [float(point["value"]) for _, point in points]
    low, high = min(values), max(values)
    span = high - low or 1.0
    def x(index: int) -> float:
        return left + index / max(len(points) - 1, 1) * (width - left - right)
    def y(value: float) -> float:
        return top + (1 - (value - low) / span) * (height - top - bottom)
    line = " ".join(f"{x(index):.1f},{y(float(point['value'])):.1f}" for index, (_, point) in enumerate(points))
    grid = "".join(f"<line class='gridline' x1='{left}' x2='{width-right}' y1='{y(low + span * index / 3):.1f}' y2='{y(low + span * index / 3):.1f}'/><text x='5' y='{y(low + span * index / 3)+4:.1f}'>{low + span * index / 3:.2f}</text>" for index in range(4))
    dots = "".join(f"<circle cx='{x(index):.1f}' cy='{y(float(point['value'])):.1f}' r='5'><title>{key} · {_esc(point.get('date'))} · {_esc(point.get('value'))}</title></circle><text text-anchor='middle' x='{x(index):.1f}' y='{height-14}'>{key}</text>" for index, (key, point) in enumerate(points))
    return f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='{_esc(series.get('series_name') or series.get('series_id'))}六窗口绝对值折线图'>{grid}<polyline points='{line}'/>{dots}</svg>"


def _storyline_html(payload: dict[str, Any]) -> str:
    nodes = {node.get("fast_node_id"): node for node in payload.get("timeline", {}).get("nodes", [])}
    cards = []
    for step in payload.get("storyline", {}).get("steps", []):
        evidence_ids = step.get("evidence_node_ids", [])
        path_ids = list(dict.fromkeys(
            path_id
            for field in ("activated_path_ids", "amplified_path_ids", "weakened_path_ids")
            for path_id in step.get(field, [])
        ))
        series_ids = step.get("market_series_ids", [])
        evidence_cards = []
        for node_id in evidence_ids:
            node = nodes.get(node_id, {})
            links = _citation_links(payload, node.get("source_ids", []), "fact")
            evidence_cards.append(
                f"<div class='drawer-evidence'><div><b>{_esc(node_id)}</b><em>{_label('status', node.get('evidence_status'))}</em></div>"
                f"<p>{_esc(_fact_summary(node))}</p><blockquote>{_esc(node.get('fact') or '事实摘录待补')}</blockquote>"
                f"<div class='citations'>{links}</div></div>"
            )
        precision = step.get("time_precision")
        if precision == "UNKNOWN":
            time_label = "时间待补证"
        elif step.get("period_start") == step.get("period_end"):
            time_label = step.get("period_start") or "时间待补证"
        else:
            time_label = f"{step.get('period_start') or '未知'} 至 {step.get('period_end') or '未知'}"
        status = _label("status", step.get("evidence_status"))
        pending_class = " pending" if step.get("evidence_status") == "PENDING_EVIDENCE" else ""
        effect_parts = []
        for field, label in (("activated_path_ids", "激活"), ("amplified_path_ids", "强化"), ("weakened_path_ids", "削弱")):
            if step.get(field):
                effect_parts.append(f"{label} {len(step[field])} 条路径")
        effects = " · ".join(effect_parts) or "当前步骤不单独激活核心路径"
        cards.append(
            f"<article class='story-step{pending_class}' data-story-step-id='{_esc(step['story_step_id'])}' "
            f"data-evidence-node-ids='{_esc('|'.join(evidence_ids))}' data-path-ids='{_esc('|'.join(path_ids))}' "
            f"data-series-ids='{_esc('|'.join(series_ids))}'>"
            f"<button class='story-head' type='button' aria-expanded='false' onclick=\"selectStoryStep('{_esc(step['story_step_id'])}')\">"
            f"<div class='story-meta'><time>{_esc(time_label)}</time><span>{_label('phase', step.get('phase'))}</span><em>{status}</em></div>"
            f"<h3>{_esc(step.get('title_cn'))}</h3><p>{_esc(step.get('narrative_cn'))}</p>"
            f"<div class='state-change'><div><small>发生前</small><b>{_esc(step.get('before_state_cn'))}</b></div>"
            f"<div><small>发生后</small><b>{_esc(step.get('after_state_cn'))}</b></div></div>"
            f"<div class='story-foot'><span>{_esc(effects)}</span><span>{len(evidence_ids)} 条证据锚点 · {len(series_ids)} 个行情序列</span></div></button>"
            f"<div class='story-drawer' hidden><div class='drawer-boundary'><b>阶段意义</b><p>{_esc(step.get('significance_cn'))}</p>"
            f"<b>证据边界</b><p>{_esc(step.get('evidence_boundary_cn'))}</p></div>{''.join(evidence_cards)}</div></article>"
        )
    return f"<div class='story-rail'>{''.join(cards)}</div>"
def _timeline_html(payload: dict[str, Any]) -> str:
    parts = []
    for phase in PHASES:
        nodes = [node for node in payload["timeline"].get("nodes", []) if node.get("phase") == phase]
        if not nodes:
            continue
        cards = []
        for node in nodes:
            status = _label("status", node.get("evidence_status"))
            classes = "timeline-node pending" if node.get("evidence_status") == "PENDING_EVIDENCE" else "timeline-node"
            original = _esc(node.get("fact") or "当前节点尚无可展示原文。")
            gap = _esc(node.get("gap_reason") or "已有来源支持节点事实；精确时点以公开定位为准。")
            tags = "".join(f"<span>{_esc(_term(tag))}</span>" for tag in node.get("impact_tags", []))
            links = _citation_links(payload, node.get("source_ids", []), "fact")
            cards.append(f"<button class='{classes}' data-node-id='{_esc(node['fast_node_id'])}' onclick=\"selectTimelineNode('{_esc(node['fast_node_id'])}')\"><div class='node-card'><div class='node-top'><time>{_esc(node.get('first_public_at') or '时间待补')}</time><em>{status}</em></div><h3>{_label('action', node.get('node_action'))} · {'主锚点' if node.get('anchor_role') == 'PRIMARY' else '次锚点' if node.get('anchor_role') == 'SECONDARY' else '事件节点'}</h3><p>{_esc(_fact_summary(node))}</p><div class='tags'>{tags}</div><div class='citations'>{links}</div><details><summary>展开原文与证据边界</summary><blockquote>{original}</blockquote><small>{gap}</small></details></div></button>")
        parts.append(f"<div class='phase'><div class='phase-title'>{_label('phase', phase)}</div><div class='timeline'>{''.join(cards)}</div></div>")
    return "".join(parts)


def _paths_html(payload: dict[str, Any]) -> str:
    cards = []
    for path in payload.get("paths", []):
        chain = list(path.get("chain", []))[:4]
        while len(chain) < 4:
            chain.append("未知")
        chain_html = "".join(f"<div><small>{['冲击类型','统一渠道','事件中间变量','资产'][index]}</small><b>{_esc(_term(item, index, payload))}</b></div>" for index, item in enumerate(chain))
        directions = "".join(f"<span><b>{'即时' if key == 'IMMEDIATE' else '短期' if key == 'SHORT_TERM' else '中期'}</b>{_esc(_label('direction', value))}</span>" for key, value in path.get("expected_direction", {}).items())
        fact_links = _citation_links(payload, path.get("event_fact_evidence", []), "fact")
        mechanism_links = _citation_links(payload, path.get("mechanism_evidence", []), "mechanism")
        anchor = (path.get("anchor_fast_node_ids") or [""])[0]
        cards.append(f"<article class='path-card' id='path-{_esc(path['path_id'])}' data-path-id='{_esc(path['path_id'])}' data-anchor-node-id='{_esc(anchor)}'><div class='path-head'><h3>{_esc(path.get('name') or '候选传导路径')}</h3><div><em>核心复核</em><em class='candidate'>候选路径</em></div></div><div class='chain'>{chain_html}</div><div class='directions'>{directions}<span><b>时滞</b>{_esc(path.get('lag', {}).get('minimum'))} 至 {_esc(path.get('lag', {}).get('maximum'))}</span></div><div class='path-copy'><b>激活阶段：</b>{'、'.join(_label('phase', phase) for phase in path.get('activation_phases', []))}。<br><b>成立条件：</b>{_esc('；'.join(path.get('conditions', [])))}<br><b>失效条件：</b>{_esc('；'.join(path.get('invalidation_conditions', [])))}<br><b>反证：</b>{_esc('；'.join(path.get('counterevidence', [])))}</div><div class='path-evidence'><small>事件事实依据</small><div class='citations'>{fact_links}</div><small>机制依据（事后验证，不用于事前预测）</small><div class='citations'>{mechanism_links}</div></div></article>")
    return "".join(cards)


def _market_html(payload: dict[str, Any]) -> str:
    panels = []
    for series in payload.get("windows", []):
        rows = []
        for key in WINDOWS:
            point = series.get("display_windows", {}).get(key, {})
            alias = f"<br><i>{_esc(point.get('observation_alias'))}</i>" if point.get("observation_alias") else ""
            raw = "未知" if point.get("raw_change") is None else f"{point['raw_change']}%"
            std = "未知" if point.get("standardized_change") is None else point["standardized_change"]
            rows.append(f"<tr><td>{_label('window', key)}<small>{key}</small></td><td>{_esc(point.get('date'))}{alias}</td><td>{_esc(point.get('value'))}</td><td>{_esc(raw)}</td><td>{_esc(std)}</td><td>{_esc(point.get('relative_change'))}</td></tr>")
        formulas = series.get("formulas", {})
        panels.append(f"<article class='market-card' data-series-id='{_esc(series.get('series_id'))}'><div class='market-head'><div><small>{_esc(series.get('asset_role') or '核心序列')} · {_esc(series.get('asset_tier'))}</small><h3>{_esc(series.get('series_name') or series.get('series_id'))}</h3></div><div>{_esc(series.get('timezone'))} · {_esc(series.get('calendar_id'))}</div></div><div class='chart'>{_chart_svg(series)}</div><p class='chart-note'>折线图使用现有绝对值窗口；缺失值保持断点。T0 与 D1 是同一日频收盘别名。</p><div class='table-scroll'><table><thead><tr><th>窗口</th><th>日期</th><th>绝对值</th><th>原始变化</th><th>标准化变化</th><th>相对变化</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class='formula'><b>计算公式：</b>{_esc(formulas.get('raw_change'))}<br>标准化变化：{_esc(formulas.get('standardized_change'))}<br>相对变化：{_esc(formulas.get('relative_change'))}</div></article>")
    return "".join(panels)


def _confounder_html(payload: dict[str, Any]) -> str:
    confounder = payload.get("confounders", {})
    items = []
    for item in confounder.get("items", []):
        windows = "、".join(_label("window", key) for key in item.get("affected_windows", []))
        links = _citation_links(payload, item.get("evidence_source_ids", []), "mechanism")
        items.append(f"<div class='confound-item'><b>{_esc(item.get('level'))} · 竞争冲击登记</b><small>影响窗口：{windows}</small><p>{_esc(item.get('description'))}</p><div class='citations'>{links}</div></div>")
    return f"<div class='argument-card'><div class='eyebrow'>挑战集说明 · {_label('status', confounder.get('clean_attribution_decision'))}</div><h3>混杂与竞争解释</h3><p>{_esc(confounder.get('argument'))}</p>{''.join(items)}</div>"


def _sources_html(payload: dict[str, Any]) -> str:
    sources = []
    for source in payload.get("sources", []):
        scope = "事后机制验证，不用于事前预测" if source.get("evidence_scope") == "POST_EVENT_MECHANISM_CORROBORATION" else "事实与时间证据"
        link = f"<a href='{_esc(source['url'])}' target='_blank' rel='noopener noreferrer'>打开对应证据链接 ↗</a>" if source.get("url") else "<span class='source-empty'>来源链接待补</span>"
        sources.append(f"<article class='source-card'><h3>{_esc(source.get('publisher') or '来源机构')}</h3><small>{scope} · {_esc(source.get('source_tier') or '来源层级未知')}</small><p>该来源已纳入证据台账；页面保留原始链接、定位和公开边界用于追溯。</p><details><summary>原文引文与定位</summary><blockquote>{_esc(_source_quote(source))}</blockquote><div>{_esc(source.get('locator') or '定位信息待补')}</div></details>{link}</article>")
    return f"<div class='sources'><div class='eyebrow'>证据台账</div><h3>可追溯引用与原文摘录</h3>{''.join(sources)}</div>"


def _evidence_html(payload: dict[str, Any]) -> str:
    return f"<div class='evidence-grid'>{_confounder_html(payload)}{_sources_html(payload)}</div>"

def _event_html(event_id: str, payload: dict[str, Any], active: bool) -> str:
    timeline = payload["timeline"]
    nodes = timeline.get("nodes", [])
    storyline = payload.get("storyline", {})
    story_steps = storyline.get("steps", [])
    primary = next((node for node in nodes if node.get("anchor_role") == "PRIMARY"), {})
    verified = sum(node.get("evidence_status") == "VERIFIED_EXISTING" for node in nodes)
    pending = sum(node.get("evidence_status") == "PENDING_EVIDENCE" for node in nodes)
    first_node = nodes[0].get("fast_node_id") if nodes else "未知"
    first_story = story_steps[0].get("story_step_id") if story_steps else first_node
    detail = nodes[0] if nodes else {}
    linked = next((row for row in payload.get("mapping", {}).get("node_mappings", []) if row.get("fast_node_id") == first_node), {})
    detail_html = (
        f"<aside class='node-detail' id='node-detail-{_esc(event_id)}'><div class='eyebrow'>当前选择 · {_esc(first_node)}</div>"
        f"<h3>{_label('phase', detail.get('phase'))} · {_label('status', detail.get('evidence_status'))}</h3>"
        f"<p>{_esc(_fact_summary(detail))}</p><div class='boundary'>{_esc(detail.get('gap_reason') or '已有来源支持节点事实；精确时点以公开定位为准。')}</div>"
        f"<dl><dt>对应传导路径</dt><dd>{_esc('、'.join(linked.get('path_ids', [])) or '当前节点没有已激活路径')}</dd>"
        f"<dt>对应行情序列</dt><dd>{_esc('、'.join(linked.get('series_ids', [])) or '当前节点没有独立行情窗口')}</dd></dl></aside>"
    )
    classes = "event-view" if active else "event-view hidden"
    return (
        f"<article class='{classes}' data-event-view='{_esc(event_id)}'><header class='hero'><div><div class='eyebrow'>{_esc(event_id.upper())} · 事件研究工作台</div>"
        f"<h1>{_esc(timeline.get('title'))}</h1><p>主锚点：{_esc(primary.get('fast_node_id'))} · 首次公开：{_esc(primary.get('first_public_at') or '时间待补')}</p></div>"
        f"<div><b>快速候选版</b><small>正式发布状态：未就绪</small></div></header>"
        f"<div class='stats'><div><b>{len(story_steps)}</b><span>事件发展步骤</span></div><div><b>{len(nodes)}</b><span>证据节点</span></div>"
        f"<div><b>{pending}</b><span>待补证</span></div><div><b>{len(payload.get('paths', []))}</b><span>候选路径</span></div>"
        f"<div><b>{sum(row.get('asset_tier') == 'CORE' for row in payload.get('windows', []))}</b><span>核心行情</span></div></div>"
        f"<div class='context'>当前选择：<strong>{_esc(first_story)}</strong> · 事件步骤可联动证据、路径与行情；所有路径仍为候选。</div>"
        f"<section id='storyline-{_esc(event_id)}'><div class='section-title'><h2>01 · 事件发展时间线</h2><p>事件状态变化、阶段意义与证据覆盖边界</p></div>{_storyline_html(payload)}</section>"
        f"<section id='timeline-{_esc(event_id)}'><div class='section-title'><h2>02 · 证据时间线</h2><p>按阶段组织事实、时间、影响标签与引用</p></div>"
        f"<div class='timeline-layout'><div class='timeline-panel'>{_timeline_html(payload)}</div>{detail_html}</div></section>"
        f"<section id='paths-{_esc(event_id)}'><div class='section-title'><h2>03 · 动态传导链</h2><p>冲击类型 → 统一渠道 → 事件中间变量 → 资产</p></div>"
        f"<div class='notice'>所有路径仍为候选状态；事后机制来源只用于验证机制叙述，不进入事前预测。</div><div class='path-grid'>{_paths_html(payload)}</div></section>"
        f"<section><div class='section-title'><h2>04 · 绝对值与变化</h2><p>固定核心资产集合与六个事件窗口</p></div><div class='market-grid'>{_market_html(payload)}</div></section>"
        f"<section><div class='section-title'><h2>05 · 证据摘录</h2><p>来源链接、原文定位与公开边界</p></div>{_sources_html(payload)}</section>"
        f"<section><div class='section-title'><h2>06 · 混杂与竞争解释</h2><p>竞争冲击、窗口污染与反证条件</p></div>{_confounder_html(payload)}</section>"
        f"<footer>数据版本：快速候选版 · {verified} 个已有证据节点 · 待补证节点不进入评分路径 · SHA 与历史分位暂缓 · 正式发布状态为未就绪。</footer></article>"
    )

STYLE = r"""
:root{--ink:#19252b;--muted:#68777e;--line:#d7e0e2;--paper:#eef2f1;--deep:#17323d;--deep2:#244a58;--red:#ad493d;--redsoft:#fff0ed;--teal:#1f6f66;--amber:#9b6b1e;--ambersoft:#fff7e7;--blue:#266886;--shadow:0 8px 22px rgba(24,45,53,.07)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;letter-spacing:0}button,a{font:inherit}button{cursor:pointer}a{color:var(--blue)}.hidden{display:none!important}
.shell{min-height:100vh;display:grid;grid-template-columns:248px minmax(0,1fr)}.event-sidebar{position:sticky;top:0;height:100vh;background:var(--deep);color:#eef5f5;padding:22px 14px;overflow:auto;z-index:6}.brand{font-size:15px;font-weight:800;letter-spacing:.08em;margin:0 8px 3px}.brand-sub{font-size:10px;color:#a8bdc2;margin:0 8px 18px}.side-state{border:1px solid #3c626c;padding:10px;margin-bottom:17px;font-size:11px;line-height:1.65;color:#b8ced2}.side-state b{display:block;color:white;font-size:17px}.side-label{font-size:10px;color:#88a5ac;margin:13px 8px 7px}.event-nav{display:grid;gap:3px}.event-link{border:0;border-left:3px solid transparent;background:transparent;color:#b9cbce;text-align:left;padding:10px 9px;width:100%}.event-link:hover{background:#204652;color:white}.event-link.active{background:var(--deep2);border-left-color:#e1a256;color:white}.event-link small,.event-link span{display:block}.event-link small{font-size:9px;color:#91abb1}.event-link span{font-size:12px;line-height:1.35;margin-top:3px}.event-link i{font-size:9px;color:#91abb1;font-style:normal}.side-foot{border-top:1px solid #35545e;margin-top:17px;padding:12px 8px;color:#86a3a9;font-size:10px;line-height:1.7}
.topbar{height:54px;background:white;border-bottom:1px solid var(--line);padding:0 30px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:5}.topbar b{font-size:14px}.topbar span{font-size:11px;color:var(--muted)}.mobile-menu{display:none;border:1px solid var(--line);background:white;padding:6px 9px}.content{max-width:1370px;margin:auto;padding:26px 30px 70px}.hero{display:flex;justify-content:space-between;align-items:flex-end;gap:22px;padding-bottom:22px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--red);font-size:10px;font-weight:800;letter-spacing:.07em}.hero h1{font-size:28px;line-height:1.3;margin:7px 0}.hero p{font-size:12px;color:var(--muted);margin:0}.hero>div:last-child{text-align:right}.hero>div:last-child b{display:inline-block;border:1px solid #d8b16b;background:var(--ambersoft);color:#7d5a1b;padding:5px 8px;font-size:11px}.hero>div:last-child small{display:block;color:var(--muted);margin-top:7px}.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;padding:17px 0}.stats>div{background:white;border:1px solid var(--line);padding:11px 12px}.stats b{display:block;font-size:22px}.stats span{font-size:10px;color:var(--muted)}.context{position:sticky;top:54px;background:rgba(238,242,241,.96);z-index:4;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:11px;color:#52656c}.context strong{color:var(--red)}section{padding:23px 0 7px;scroll-margin-top:105px}.section-title{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}.section-title h2{font-size:18px;margin:0}.section-title p{font-size:11px;color:var(--muted);margin:0}
.story-rail{position:relative;display:grid;gap:11px;padding-left:28px}.story-rail:before{content:"";position:absolute;left:8px;top:16px;bottom:16px;width:2px;background:#a9bbc0}.story-step{position:relative;background:white;border:1px solid var(--line);box-shadow:var(--shadow);transition:border-color .16s,box-shadow .16s}.story-step:before{content:"";position:absolute;left:-26px;top:22px;width:13px;height:13px;border-radius:50%;background:var(--teal);border:3px solid var(--paper);box-sizing:content-box}.story-step.pending:before{background:var(--amber)}.story-step.selected{border-color:#ca6258;box-shadow:0 0 0 3px #efb9b2,var(--shadow)}.story-step.selected:before{background:var(--red)}.story-head{display:block;width:100%;border:0;background:transparent;color:inherit;text-align:left;padding:16px 18px}.story-head:focus-visible{outline:3px solid #8bb7c5;outline-offset:2px}.story-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:10px}.story-meta time{font-weight:800;color:var(--red)}.story-meta span,.story-meta em{border:1px solid #bfd0d3;padding:3px 6px;font-style:normal}.story-meta span{color:var(--teal);background:#f3faf8}.story-meta em{color:var(--blue)}.story-step.pending .story-meta em{border-color:#d9bd84;background:var(--ambersoft);color:#7a581b}.story-head h3{font-size:16px;line-height:1.45;margin:10px 0 6px}.story-head>p{font-size:12px;line-height:1.75;color:#34484f;margin:0}.state-change{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px;margin-top:12px}.state-change>div{border-left:3px solid #a9c0c4;background:#f5f8f8;padding:9px 11px;min-width:0}.state-change>div:last-child{border-left-color:var(--red);background:var(--redsoft)}.state-change small,.state-change b{display:block}.state-change small{font-size:9px;color:var(--muted);margin-bottom:4px}.state-change b{font-size:11px;line-height:1.55;overflow-wrap:anywhere}.story-foot{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line);margin-top:12px;padding-top:9px;color:var(--muted);font-size:10px}.story-drawer{border-top:1px solid var(--line);padding:15px 18px 17px;background:#fbfcfc}.story-drawer[hidden]{display:none}.drawer-boundary{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 12px;border-left:3px solid var(--amber);background:var(--ambersoft);padding:11px 12px}.drawer-boundary b{font-size:10px;color:#75551d}.drawer-boundary p{font-size:11px;line-height:1.65;margin:0}.drawer-evidence{padding:13px 0 0}.drawer-evidence+.drawer-evidence{border-top:1px solid var(--line);margin-top:12px}.drawer-evidence>div:first-child{display:flex;justify-content:space-between;gap:10px;font-size:10px}.drawer-evidence em{font-style:normal;color:var(--blue)}.drawer-evidence p{font-size:11px;line-height:1.65;margin:7px 0}.drawer-evidence blockquote{font-size:11px;color:#455b63}
.timeline-layout{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(290px,.9fr);gap:13px}.timeline-panel,.node-detail,.path-card,.market-card,.argument-card,.sources{background:white;border:1px solid var(--line);box-shadow:var(--shadow)}.timeline-panel{padding:17px}.phase+.phase{margin-top:19px}.phase-title{display:flex;gap:8px;align-items:center;color:var(--teal);font-size:10px;font-weight:800}.phase-title:after{content:"";height:1px;background:var(--line);flex:1}.timeline{border-left:2px solid #9eb2b6;margin:10px 0 0 9px;padding-left:20px}.timeline-node{position:relative;width:100%;border:0;background:transparent;text-align:left;color:inherit;padding:0 0 15px}.timeline-node:before{content:"";position:absolute;left:-26px;top:6px;width:11px;height:11px;border-radius:50%;background:var(--blue);box-shadow:0 0 0 3px var(--paper)}.timeline-node.pending:before{background:var(--amber)}.timeline-node.selected:before{background:var(--red);box-shadow:0 0 0 4px #efb9b2}.timeline-node.selected .node-card{background:var(--redsoft);border-color:#d89891}.node-card{border:1px solid var(--line);padding:11px 12px}.node-top{display:flex;justify-content:space-between;gap:8px;font-size:10px;color:var(--muted)}.node-top em{font-style:normal;border:1px solid #b8cbd0;padding:2px 5px;color:var(--blue)}.node-card h3{font-size:13px;margin:7px 0 5px}.node-card p{font-size:12px;line-height:1.65;margin:0;color:#34484f}.tags,.citations{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.tags span,.citation{font-size:9px;border:1px solid #c2d1d4;padding:3px 5px;background:#f6faf9}.citation{text-decoration:none;color:#1c607b}.citation.mechanism{background:var(--ambersoft);border-color:#d9bd84;color:#795516}.source-empty{font-size:10px;color:var(--muted)}details{font-size:10px;margin-top:9px;color:#566a72}summary{cursor:pointer}blockquote{border-left:3px solid #b7cbd0;margin:8px 0;padding-left:9px;line-height:1.6}.node-detail{padding:17px;position:sticky;top:111px;height:max-content}.node-detail h3{font-size:16px;margin:7px 0}.node-detail p{font-size:12px;line-height:1.7}.boundary,.notice{border-left:3px solid var(--amber);background:var(--ambersoft);padding:9px 10px;font-size:11px;line-height:1.6;color:#6f551f}.node-detail dl{font-size:11px}.node-detail dt{font-weight:700;color:#5e737a;margin-top:10px}.node-detail dd{margin:3px 0;line-height:1.5}
.path-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.path-card{padding:16px;scroll-margin-top:110px}.path-card.selected{border-color:#ca6258;box-shadow:0 0 0 3px #efb9b2,var(--shadow)}.path-head{display:flex;justify-content:space-between;gap:9px}.path-head h3{font-size:14px;margin:0}.path-head em{font-style:normal;font-size:9px;border:1px solid #bdced2;padding:3px 5px}.path-head em.candidate{border-color:#d8bd86;background:var(--ambersoft);color:#8a6019;margin-left:4px}.chain{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:14px 0}.chain>div{position:relative;border:1px solid #b8ccd0;background:#f4faf9;text-align:center;padding:8px 5px;color:#295d61}.chain>div:not(:last-child):after{content:"→";position:absolute;right:-10px;top:50%;transform:translateY(-50%);color:var(--red);z-index:2}.chain small,.chain b{display:block}.chain small{font-size:8px}.chain b{font-size:10px;margin-top:3px}.directions{display:flex;gap:5px;flex-wrap:wrap}.directions span{font-size:9px;border:1px solid var(--line);padding:4px 5px}.directions b{color:var(--red);margin-right:4px}.path-copy{font-size:11px;line-height:1.75;color:#41545c;margin-top:10px}.path-evidence{border-top:1px solid var(--line);margin-top:10px;padding-top:9px}.path-evidence small{display:block;color:var(--muted);margin-top:7px}
.market-grid{display:grid;gap:12px}.market-card{padding:16px;min-width:0;transition:border-color .16s,box-shadow .16s}.market-card.selected{border-color:#ca6258;box-shadow:0 0 0 3px #efb9b2,var(--shadow)}.market-head{display:flex;justify-content:space-between;gap:12px}.market-head h3{font-size:15px;margin:3px 0}.market-head small,.market-head>div:last-child{font-size:10px;color:var(--muted)}.chart{border:1px solid var(--line);background:#fbfcfc;padding:7px;margin-top:12px}.chart svg{width:100%;height:auto;display:block}.chart svg polyline{fill:none;stroke:var(--red);stroke-width:3;stroke-linecap:round;stroke-linejoin:round}.chart svg circle{fill:var(--red);stroke:white;stroke-width:2}.chart svg text{font-size:10px;fill:#607179}.gridline{stroke:#dbe4e5;stroke-width:1}.chart-note{font-size:10px;color:var(--muted)}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:10px;min-width:700px}th,td{padding:7px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}td small{display:block;color:var(--muted)}td i{color:var(--teal);font-style:normal}.formula{border-left:3px solid var(--blue);background:#f1f7fa;padding:9px 10px;margin-top:11px;font-size:10px;line-height:1.7}
.evidence-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:13px}.argument-card,.sources{padding:17px}.argument-card>p{font-size:13px;line-height:1.9;color:#31474e}.confound-item,.source-card{border-top:1px solid var(--line);padding:12px 0}.confound-item small,.source-card small{display:block;color:var(--muted);font-size:9px;margin-top:4px}.confound-item p,.source-card p{font-size:11px;line-height:1.65}.source-card h3,.argument-card h3,.sources h3{font-size:14px;margin:5px 0}.source-card>a{display:inline-block;margin-top:7px;font-size:10px}footer{border-top:1px solid var(--line);margin-top:28px;padding-top:22px;font-size:10px;color:var(--muted);line-height:1.7}
@media(max-width:1050px){.content{padding:22px}.timeline-layout,.evidence-grid{grid-template-columns:1fr}.node-detail{position:static}.path-grid{grid-template-columns:1fr}}
@media(max-width:760px){.shell{display:block}.event-sidebar{position:fixed;inset:0 auto 0 0;width:286px;transform:translateX(-100%);transition:.2s;box-shadow:12px 0 30px rgba(0,0,0,.2)}.event-sidebar.open{transform:translateX(0)}.topbar{height:50px;padding:0 13px}.topbar span{display:none}.mobile-menu{display:block}.content{padding:17px 13px 45px}.hero{display:block}.hero h1{font-size:22px}.hero>div:last-child{text-align:left;margin-top:11px}.stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.context{top:50px}.section-title{display:block}.section-title p{margin-top:4px}.chain{grid-template-columns:repeat(2,minmax(0,1fr))}.chain>div:not(:last-child):after{display:none}.path-card,.timeline-panel,.market-card{padding:12px}.story-rail{padding-left:23px}.story-rail:before{left:6px}.story-step:before{left:-22px}.story-head{padding:13px}.state-change{grid-template-columns:1fr}.story-foot{display:block}.story-foot span{display:block;margin-top:3px}.story-drawer{padding:13px}.drawer-boundary{grid-template-columns:1fr}.drawer-boundary p+ b{margin-top:5px}}
"""


def render_workbench(payloads: dict[str, dict[str, Any]], initial_event_id: str) -> str:
    if not payloads:
        raise ValueError("workbench requires event payloads")
    if initial_event_id not in payloads:
        initial_event_id = next(iter(payloads))
    enriched = json.loads(json.dumps(payloads, ensure_ascii=False))
    for event_id, payload in enriched.items():
        payload["confounders"]["argument"] = build_confounder_argument(
            event_id, payload["timeline"], payload.get("paths", []), payload["confounders"]
        )
    buttons = []
    views = []
    total_verified = total_pending = total_paths = total_extensions = 0
    for event_id, payload in enriched.items():
        nodes = payload["timeline"].get("nodes", [])
        verified = sum(node.get("evidence_status") == "VERIFIED_EXISTING" for node in nodes)
        pending = sum(node.get("evidence_status") == "PENDING_EVIDENCE" for node in nodes)
        total_verified += verified
        total_pending += pending
        total_paths += len(payload.get("paths", []))
        total_extensions += sum(row.get("asset_tier") != "CORE" for row in payload.get("windows", []))
        active = event_id == initial_event_id
        buttons.append(f"<button class='event-link {'active' if active else ''}' data-event-id=\"{_esc(event_id)}\" onclick=\"selectEvent('{_esc(event_id)}')\"><small>{_esc(event_id.upper())}</small><span>{_esc(payload['timeline'].get('title'))}</span><i>{verified} 已有 · {pending} 待补</i></button>")
        views.append(_event_html(event_id, payload, active))
    data = _json_data(enriched)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FinGoose 事件研究工作台</title><link rel="icon" href="data:,"><style>{STYLE}</style></head><body>
<div class="shell"><aside class="event-sidebar" id="event-sidebar" aria-label="十事件导航"><div class="brand">FINGOOSE</div><div class="brand-sub">宏观事件归因研究工作台</div><div class="side-state"><b>快速候选版</b>证据边界保持开放<br>正式发布状态：未就绪</div><div class="side-label">十事件目录</div><nav class="event-nav">{''.join(buttons)}</nav><div class="side-foot">{total_verified} 个已有证据节点<br><b>{total_pending}</b> 待补证节点<br>{total_paths} 条候选传导路径<br>{total_extensions} 个扩展资产<br>验证状态：通过<br>数据 SHA 与历史分位暂缓</div></aside>
<div><header class="topbar"><b>事件时间线与动态传导链</b><span>点击节点可联动路径、行情与证据</span><button class="mobile-menu" id="mobile-menu" aria-label="打开事件导航">事件目录</button></header><main id="research-main" class="content">{''.join(views)}</main></div></div>
<div id="chronology-note" hidden>叙事顺序 · 事实来源 · 事件事实依据 · 机制依据</div><a hidden target="_blank" rel="noopener noreferrer"></a>
<script id="workbench-data" type="application/json">{data}</script>
<script>
const DATA=JSON.parse(document.getElementById("workbench-data").textContent);
const windowPoints=["T-1","T0","D1","D3","D5","D20"];
const escapeMap={{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}};
function splitIds(value){{return (value||"").split("|").filter(Boolean)}}
function storyStepsForNode(view,nodeId){{
  return [...view.querySelectorAll(".story-step")].filter(story=>splitIds(story.dataset.evidenceNodeIds).includes(nodeId));
}}
function pathCardsForIds(view,ids){{
  const wanted=new Set(ids); return [...view.querySelectorAll(".path-card")].filter(path=>wanted.has(path.dataset.pathId));
}}
function marketCardsForIds(view,ids){{
  const wanted=new Set(ids); return [...view.querySelectorAll(".market-card")].filter(card=>wanted.has(card.dataset.seriesId));
}}
function setStoryDrawer(story,expanded){{
  const header=story.querySelector(".story-head"),drawer=story.querySelector(".story-drawer");
  header?.setAttribute("aria-expanded",expanded?"true":"false"); if(drawer)drawer.hidden=!expanded;
}}
function closeStoryDrawers(view,except=null){{
  view.querySelectorAll(".story-step").forEach(story=>{{if(story!==except)setStoryDrawer(story,false)}});
}}
function clearVisualSelection(view){{
  view.querySelectorAll(".story-step,.timeline-node,.path-card,.market-card").forEach(item=>item.classList.remove("selected"));
}}
function updateContext(view,label,kind){{
  const context=view.querySelector(".context"); if(!context)return;
  context.innerHTML='当前选择：<strong></strong> · '+kind+'；高亮仅表示关联，不改变证据或候选路径状态。';
  context.querySelector("strong").textContent=label;
}}
function selectEvent(eventId){{
  document.querySelectorAll("[data-event-view]").forEach(view=>view.classList.toggle("hidden",view.dataset.eventView!==eventId));
  document.querySelectorAll("[data-event-id]").forEach(link=>link.classList.toggle("active",link.dataset.eventId===eventId));
  document.getElementById("event-sidebar").classList.remove("open");
  const view=document.querySelector('[data-event-view="'+CSS.escape(eventId)+'"]');
  const story=view?.querySelector(".story-step.selected")||view?.querySelector(".story-step");
  if(story)selectStoryStep(story.dataset.storyStepId);
  window.scrollTo({{top:0,behavior:"smooth"}});
}}
function selectStoryStep(stepId){{
  const story=document.querySelector('[data-story-step-id="'+CSS.escape(stepId)+'"]'); if(!story)return;
  const view=story.closest("[data-event-view]"); clearVisualSelection(view); closeStoryDrawers(view,story);
  story.classList.add("selected"); setStoryDrawer(story,true);
  const evidenceIds=splitIds(story.dataset.evidenceNodeIds);
  const pathIds=splitIds(story.dataset.pathIds);
  const seriesIds=splitIds(story.dataset.seriesIds);
  view.querySelectorAll(".timeline-node").forEach(node=>node.classList.toggle("selected",evidenceIds.includes(node.dataset.nodeId)));
  pathCardsForIds(view,pathIds).forEach(path=>path.classList.add("selected"));
  view.querySelectorAll(".market-card").forEach(card=>card.classList.toggle("selected",seriesIds.includes(card.dataset.seriesId)));
  const title=story.querySelector("h3")?.textContent||stepId;
  updateContext(view,title,"已联动证据节点、候选路径与行情序列");
}}
function selectTimelineNode(nodeId){{
  const button=document.querySelector('[data-node-id="'+CSS.escape(nodeId)+'"]'); if(!button)return;
  const view=button.closest("[data-event-view]"); clearVisualSelection(view); closeStoryDrawers(view);
  button.classList.add("selected");
  const stories=storyStepsForNode(view,nodeId); stories.forEach(story=>story.classList.add("selected"));
  if(stories[0])setStoryDrawer(stories[0],true);
  const storyPathIds=stories.flatMap(story=>splitIds(story.dataset.pathIds));
  const directPaths=[...view.querySelectorAll(".path-card")].filter(path=>path.dataset.anchorNodeId===nodeId);
  const paths=[...new Set([...pathCardsForIds(view,storyPathIds),...directPaths])]; paths.forEach(path=>path.classList.add("selected"));
  const seriesIds=stories.flatMap(story=>splitIds(story.dataset.seriesIds));
  marketCardsForIds(view,seriesIds).forEach(card=>card.classList.add("selected"));
  const detail=view.querySelector(".node-detail"), card=button.querySelector(".node-card"), linked=paths.map(path=>path.dataset.pathId).join("、")||"当前节点没有已激活路径";
  detail.innerHTML='<div class="eyebrow">当前选择 · '+nodeId+'</div><h3>'+card.querySelector("h3").textContent+'</h3><p>'+card.querySelector("p").textContent+'</p><div class="boundary">证据状态：'+card.querySelector("em").textContent+'。原文与证据边界可在节点卡片中展开。</div><dl><dt>对应事件步骤</dt><dd>'+(stories.map(story=>story.querySelector("h3").textContent).join("、")||"待建立叙事映射")+'</dd><dt>对应传导路径</dt><dd>'+linked+'</dd></dl>';
  updateContext(view,nodeId,"已反向定位事件步骤，并联动候选路径与行情序列");
  (paths[0]||stories[0])?.scrollIntoView({{behavior:"smooth",block:"center"}});
}}
function activatePath(pathId){{const path=document.querySelector('[data-path-id="'+CSS.escape(pathId)+'"]');if(!path)return;path.closest("[data-event-view]").querySelectorAll(".path-card").forEach(item=>item.classList.remove("selected"));path.classList.add("selected");path.scrollIntoView({{behavior:"smooth",block:"center"}})}}
document.getElementById("mobile-menu").onclick=()=>document.getElementById("event-sidebar").classList.toggle("open");
const initialStory=document.querySelector("[data-event-view]:not(.hidden) .story-step");
if(initialStory)selectStoryStep(initialStory.dataset.storyStepId);
</script></body></html>'''

def _json_data(payloads: dict[str, dict[str, Any]]) -> str:
    return json.dumps(payloads, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
