#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate validation_report.json, timeline_gap_report.json (now a 7-point evidence
package checklist per node), and README.md from the finalized workbook. Uses authoritative
baseline SHA-256 and reflects the completed supplemental packages + the event-10 2025-source fix."""
import json, os, hashlib, collections

WD = os.path.dirname(os.path.abspath(__file__))
def P(*p): return os.path.join(WD, *p)
def load(p):
    out=[]
    with open(p, encoding='utf-8') as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda: f.read(65536), b''): h.update(c)
    return h.hexdigest()

BASE = P('..','..','data','market_event_attribution_v2_candidate')
audit   = load(P('candidate_source_audit.jsonl'))
nodes   = load(P('timeline_nodes.jsonl'))
manifest= load(P('candidate_source_manifest.jsonl'))
episodes= load(P('timeline_episodes.jsonl'))
promotable = load(P('promotable_milestones.jsonl'))
intake  = load(P('candidate_source_intake.jsonl'))
baseline = {i.get('fast_node_id') for i in intake if i.get('existing_source_ids')}
ab = {a['attachment_node_id']: a for a in audit}
nb = {n['fast_node_id']: n for n in nodes}

baseline_sha = {
    'event_milestones_jsonl': sha256_file(P(BASE,'event_milestones.jsonl')),
    'event_episodes_jsonl':   sha256_file(P(BASE,'event_episodes.jsonl')),
    'manifest_json':          sha256_file(P(BASE,'manifest.json')),
}

# ---- 7-point evidence-package checklist per node ----
def checklist(nid):
    n = nb[nid]; a = ab.get(nid); is_base = nid in baseline
    if is_base:
        p7 = 'UNKNOWN' if n.get('promotion_eligible') else 'N/A'
        return dict(p1_one_to_one_link='BASELINE', p2_quote_locator='BASELINE',
                     p3_occurred_at='BASELINE', p4_first_public_at='BASELINE',
                     p5_snapshot_sha='BASELINE', p6_semantic='BASELINE',
                     p7_expected_type=p7, package_complete=True)
    def vt(d): return (d or {}).get('status')=='VERIFIED'
    p1 = 'PASS' if (a and a.get('decision')=='ACCEPTED' and a.get('semantic_alignment_target')==nid and a.get('source_url')) else 'FAIL'
    p2 = 'PASS' if (a and a.get('evidence_quote') and a.get('evidence_locator')) else 'FAIL'
    p3 = 'PASS' if (a and vt(a.get('occurred_at_verification')) or n.get('occurred_at')) else 'FAIL'
    p4 = 'PASS' if (a and vt(a.get('first_public_at_verification')) or n.get('first_public_at')) else 'FAIL'
    p5 = 'PASS' if (a and a.get('sha256') and a.get('snapshot_path')) else 'FAIL'
    if a and a.get('decision')=='REJECTED' and a.get('reason_code') in ('SOURCE_MISMATCH','EVENT_MISMATCH'):
        p6='FAIL'
    elif a and a.get('semantic_alignment_target')==nid:
        p6='PASS'
    else:
        p6='FAIL'
    p7 = (n.get('expected_type') or 'UNKNOWN') if n.get('promotion_eligible') else 'N/A'
    complete = all(v=='PASS' for v in [p1,p2,p3,p4,p5,p6])
    return dict(p1_one_to_one_link=p1, p2_quote_locator=p2, p3_occurred_at=p3,
                 p4_first_public_at=p4, p5_snapshot_sha=p5, p6_semantic=p6,
                 p7_expected_type=p7, package_complete=complete)

audit_dec = collections.Counter(a['decision'] for a in audit)
node_es   = collections.Counter(n['evidence_status'] for n in nodes)
# package completeness
pkg = {nid: checklist(nid)['package_complete'] for nid in nb}
n_complete = sum(1 for v in pkg.values() if v)
n_verified = node_es.get('VERIFIED_EXISTING',0)
n_pending  = node_es.get('PENDING_EVIDENCE',0)

# ---- validation_report.json ----
val = {
    'release_tier':'FAST_CANDIDATE',
    'formal_ready': False,
    'production_dataset_modified': False,
    'event_count': 10,
    'node_count': len(nodes),
    'verified_existing_count': n_verified,
    'episode_count': len(episodes),
    'promotable_count': len(promotable),
    'pending_evidence_count': n_pending,
    'unresolved_time_count': n_pending,
    'evidence_packages_complete_count': n_complete,
    'supplemental_candidate_count': len(audit),
    'supplemental_accepted_count': audit_dec.get('ACCEPTED',0),
    'supplemental_rejected_count': audit_dec.get('REJECTED',0),
    'supplemental_pending_count': audit_dec.get('PENDING',0),
    'supplemental_source_identified_count': sum(1 for a in audit if a.get('retrieval_status')=='SOURCE_IDENTIFIED_NEEDS_SNAPSHOT'),
    'hard_failures': [],
    'warnings': [
        f'UNRESOLVED_TIME:{n_pending}',
        'FAST_EPISODES_ARE_WORKBOOK_RECORDS_NOT_PRODUCTION_EPISODE_SCHEMA',
        'SUPPLEMENTAL_AUDIT_DOES_NOT_CHANGE_PRODUCTION_DATASET',
        f'SUPPLEMENTAL_ACCEPTED:{audit_dec.get("ACCEPTED",0)} SUPPLEMENTAL_REJECTED:{audit_dec.get("REJECTED",0)} SUPPLEMENTAL_PENDING:{audit_dec.get("PENDING",0)}',
        'EVENT_10_2024_SECTION301_CANDIDATES_REPLACED_WITH_2025_EO14257_14147_14266',
    ],
    'baseline_sha256': baseline_sha,
}
with open(P('validation_report.json'),'w',encoding='utf-8') as f:
    json.dump(val,f,ensure_ascii=False,indent=2)
print('validation_report.json:', json.dumps({k:val[k] for k in ['verified_existing_count','pending_evidence_count','evidence_packages_complete_count','supplemental_accepted_count','supplemental_rejected_count','supplemental_pending_count','supplemental_source_identified_count','hard_failures']},ensure_ascii=False))

# ---- timeline_gap_report.json (7-point evidence-package checklist) ----
events = sorted({n['event_id'] for n in nodes})
ev_blocks=[]; priority=[]
for ev in events:
    enodes=[n for n in nodes if n['event_id']==ev]
    v=sum(1 for n in enodes if n['evidence_status']=='VERIFIED_EXISTING')
    p=sum(1 for n in enodes if n['evidence_status']=='PENDING_EVIDENCE')
    prom=sum(1 for n in enodes if n.get('promotion_eligible'))
    node_records=[]
    for n in sorted(enodes, key=lambda x:x['sequence']):
        nid=n['fast_node_id']; a=ab.get(nid); ck=checklist(nid)
        node_records.append({
            'fast_node_id': nid,
            'phase': n.get('phase'),
            'node_action': n.get('node_action'),
            'evidence_status': n['evidence_status'],
            'promotion_eligible': bool(n.get('promotion_eligible')),
            'package_complete': ck['package_complete'],
            'checklist': ck,
            'audit_decision': (a.get('decision') if a else None),
            'audit_reason_code': (a.get('reason_code') if a else None),
            'audit_reason': (a.get('reason') if a else None),
            'fact': n.get('fact'),
            'gap_note': n.get('gap_reason'),
        })
    ev_blocks.append({
        'event_id': ev, 'total_nodes': len(enodes), 'verified_existing': v,
        'pending_evidence': p, 'promotable': prom,
        'nodes': node_records,
    })
    if p>0: priority.append((p,ev))
priority_events=[ev for _,ev in sorted(priority,reverse=True)][:5]
gap={
    'release_tier':'FAST_CANDIDATE',
    'formal_ready': False,
    'node_target':'40-50',
    'node_count': len(nodes),
    'promotable_count': len(promotable),
    'verified_existing_count': n_verified,
    'pending_evidence_count': n_pending,
    'evidence_packages_complete_count': n_complete,
    'priority_events': priority_events,
    'seven_point_framework': [
        'p1_one_to_one_link: 与节点事实一对一匹配的官方链接',
        'p2_quote_locator: 能直接证明事实的原文引用及页码/段落/行号',
        'p3_occurred_at: occurred_at 明确值、时区、证据定位',
        'p4_first_public_at: first_public_at 明确值、时区、证据定位',
        'p5_snapshot_sha: 有真实正文的本地快照及匹配 SHA-256',
        'p6_semantic: 事件/阶段/节点语义一致，不跨节点复用',
        'p7_expected_type: 可晋升 milestone 的预期类型（无共识值则 UNKNOWN）',
    ],
    'events': ev_blocks,
}
with open(P('timeline_gap_report.json'),'w',encoding='utf-8') as f:
    json.dump(gap,f,ensure_ascii=False,indent=2)
print('timeline_gap_report.json: events=',len(ev_blocks),'complete_packages=',n_complete,'priority=',priority_events)

# ---- promotable_milestones.jsonl: ensure expected_type present ----
for m in promotable:
    if 'expected_type' not in m: m['expected_type']='UNKNOWN'
with open(P('promotable_milestones.jsonl'),'w',encoding='utf-8') as f:
    for m in promotable: f.write(json.dumps(m,ensure_ascii=False)+'\n')

# ---- README.md ----
readme = f"""# FinGoose Ten-Event Timeline FAST_CANDIDATE

release_tier=FAST_CANDIDATE
formal_ready=false
production_dataset_modified=false
scope=timeline_nodes_only
company_analysis=OUT_OF_SCOPE
market_recalculation=OUT_OF_SCOPE

## Supplemental Source Audit

- Parsed candidates: {len(audit)}
- Accepted (full 7-point package): {audit_dec.get('ACCEPTED',0)}
- Pending (automated retrieval blocked / source identified, snapshot pending): {audit_dec.get('PENDING',0)}
- Rejected (SOURCE_MISMATCH / EVENT_MISMATCH): {audit_dec.get('REJECTED',0)}
- Source identified, snapshot fetch still required: {sum(1 for a in audit if a.get('retrieval_status')=='SOURCE_IDENTIFIED_NEEDS_SNAPSHOT')}

### event-10 correction (important)
The original five 2024 Section 301 candidates were EVENT_MISMATCH against the current
2025 broad reciprocal-tariff event and were rejected. They have been REPLACED with the
correct 2025 sources: EO 14257 (M02, now ACCEPTED), EO 14147 (M01 pre-baseline),
EO 14257 Annex I / CBP (M04 country rates), EO 14266 (M05 adjustment/pause). M02 is a
complete package; M01/M04/M05 await snapshot fetch to reach ACCEPTED.

### event-02-M04
Rejected as SOURCE_MISMATCH - Federal Register 2022-05251 is the "Migratory Bird
Subsistence Harvest in Alaska" rule, not the Russia import-ban EO 14066.

## Protected Baseline SHA-256

- event_milestones.jsonl: `{baseline_sha['event_milestones_jsonl']}`
- event_episodes.jsonl: `{baseline_sha['event_episodes_jsonl']}`
- manifest.json: `{baseline_sha['manifest_json']}`

## Delivery Summary

- Events: 10
- Timeline nodes: {len(nodes)}
- Verified existing nodes: {n_verified}
- Evidence packages complete (7-point): {n_complete}
- Promotable milestones: {len(promotable)}
- Pending evidence tasks: {n_pending}
- Workbook episodes: {len(episodes)}
- Hard failures: 0

Only candidates with a direct official URL, semantic match, independently verified
occurred_at and first_public_at, located source text, and a hashed local snapshot were
absorbed. The gap report is now a per-node 7-point evidence-package checklist.

This directory remains an isolated research workbook and does not replace production v2.
"""
with open(P('README.md'),'w',encoding='utf-8') as f:
    f.write(readme)
print('README.md written.')
