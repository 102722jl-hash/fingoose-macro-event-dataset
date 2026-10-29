#!/usr/bin/env python3
"""Apply WebFetch second-pass confirmations to the audit + node files.

The audit file uses field names:
  attachment_node_id, decision, reason, reason_code, retrieval_status,
  source_url, publisher, source_tier, snapshot_path, sha256, claimed_quote,
  evidence_quote, occurred_at_verification, first_public_at_verification,
  fact_status, semantic_alignment_target, candidate_url, canonical_url ...
"""

import json, os

WORK = r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\work\timeline_fast_candidate_v2"

# WebFetch-confirmed outcomes.
# nid -> dict(decision, reason_code, reason, evidence_quote, fpa, occ, snapshot, hash)
WEB = {
    # ── ACCEPTED (WebFetch confirmed quoted text on live official page) ──
    'fast-event-05-M05': dict(
        decision='ACCEPTED', reason_code='QUOTE_VERIFIED_WEBFETCH',
        reason='WebFetch fetched live FDIC page and confirmed title "JPMorgan Chase Bank, National Association, Columbus, Ohio Assumes All the Deposits of First Republic Bank, San Francisco, California". Published May 1, 2023.',
        evidence_quote='JPMorgan Chase Bank, National Association, Columbus, Ohio Assumes All the Deposits of First Republic Bank, San Francisco, California.',
        fpa='2023-05-01T07:30:00+00:00', occ=None,
        snapshot='sources/cand_fast-event-05-M05.html', hash='WEBFETCH_VERIFIED'),
    'fast-event-01-M02': dict(
        decision='ACCEPTED', reason_code='QUOTE_VERIFIED_WEBFETCH',
        reason='WebFetch fetched Gazzetta Ufficiale decree 20A01558 (DPCM 9 March 2020) and confirmed "applicabili sull\'intero territorio nazionale". Published March 9, 2020.',
        evidence_quote='DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI 9 marzo 2020 ... applicabili sull\'intero territorio nazionale. (20A01558)',
        fpa='2020-03-09T21:00:00+00:00', occ=None,
        snapshot='sources/cand_fast-event-01-M02.html', hash='WEBFETCH_VERIFIED'),
    'fast-event-08-M01': dict(
        decision='ACCEPTED', reason_code='QUOTE_VERIFIED_WEBFETCH',
        reason='WebFetch fetched BOJ July 28 2023 statement and confirmed "conduct yield curve control with greater flexibility" and "offer to purchase 10-year JGBs at 1.0 percent".',
        evidence_quote='The Bank will conduct YCC with greater flexibility ... offer to purchase 10-year JGBs at 1.0 percent',
        fpa='2023-07-28T03:00:00+00:00', occ=None,
        snapshot='sources/cand_fast-event-08-M01.html', hash='WEBFETCH_VERIFIED'),
    'fast-event-03-M02': dict(
        decision='ACCEPTED', reason_code='QUOTE_VERIFIED_WEBFETCH',
        reason='WebFetch fetched BLS CPI news release (USDL-22-0191, embargoed until 8:30 a.m. ET February 10, 2022) and confirmed "The Consumer Price Index for All Urban Consumers (CPI-U) increased 7.5 percent over the last 12 months".',
        evidence_quote='The Consumer Price Index for All Urban Consumers (CPI-U) increased 7.5 percent over the last 12 months',
        fpa='2022-02-10T13:30:00+00:00', occ=None,
        snapshot='sources/cand_fast-event-03-M02.html', hash='WEBFETCH_VERIFIED'),
    'fast-event-08-M03': dict(
        decision='ACCEPTED', reason_code='QUOTE_VERIFIED_WEBFETCH',
        reason='WebFetch fetched BOJ March 19 2024 statement and confirmed "The Bank will encourage the uncollateralized overnight call rate to remain at around 0 to 0.1 percent" and discontinuation of YCC / negative interest rate policy.',
        evidence_quote='The Bank will encourage the uncollateralized overnight call rate to remain at around 0 to 0.1 percent ... QQE with Yield Curve Control and the negative interest rate policy to date have fulfilled their roles',
        fpa='2024-03-19T03:30:00+00:00', occ=None,
        snapshot='sources/cand_fast-event-08-M03.html', hash='WEBFETCH_VERIFIED'),
    # ── NEEDS_REVIEW (WebFetch confirmed failure with specific cause) ──
    'fast-event-02-M05': dict(
        decision='NEEDS_REVIEW', reason_code='RETRIEVAL_404',
        reason='WebFetch returned Error 404: Page Not Found for the White House joint SWIFT statement URL. Page moved or archived; candidate URL not resolvable.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-02-M04': dict(
        decision='NEEDS_REVIEW', reason_code='WRONG_DOCUMENT',
        reason='WebFetch fetched the Federal Register URL but it returns document 2022-05251 (87 FR 14232, Fish and Wildlife Service Alaska migratory bird rule), NOT EO 14066 (87 FR 13660, Russian oil imports). Candidate URL points to wrong FR entry.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-05-M01': dict(
        decision='NEEDS_REVIEW', reason_code='INVALID_URL',
        reason='WebFetch returned NoSuchKey from SEC S3: the EDGAR file does not exist at this path. Candidate URL is malformed or the filing was relocated.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-04-M01': dict(
        decision='NEEDS_REVIEW', reason_code='SITE_BLOCKED',
        reason='nhc.gov.cn returned empty body via WebFetch. Chinese government site blocks automated retrieval; manual verification required.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-02-M02': dict(
        decision='NEEDS_REVIEW', reason_code='SITE_BLOCKED',
        reason='en.kremlin.ru returned empty body via WebFetch. Russian government site blocks automated retrieval; manual verification required.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-07-M04': dict(
        decision='NEEDS_REVIEW', reason_code='SITE_BLOCKED',
        reason='defense.gov returned empty body via WebFetch. Site blocks automated retrieval; manual verification required.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-06-M02': dict(
        decision='NEEDS_REVIEW', reason_code='SITE_BLOCKED',
        reason='spa.gov.sa returned only the agency-name shell with no article body via WebFetch. Site blocks automated retrieval; manual verification required.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
    'fast-event-06-M04': dict(
        decision='NEEDS_REVIEW', reason_code='SITE_BLOCKED',
        reason='spa.gov.sa returned only the agency-name shell with no article body via WebFetch. Site blocks automated retrieval; manual verification required.',
        evidence_quote='', fpa=None, occ=None, snapshot=None, hash=None),
}

def load_jsonl(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]

def write_jsonl(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

audit_path = os.path.join(WORK, "candidate_source_audit.jsonl")
manifest_path = os.path.join(WORK, "candidate_source_manifest.jsonl")
nodes_path = os.path.join(WORK, "timeline_nodes.jsonl")
intake_path = os.path.join(WORK, "candidate_source_intake.jsonl")

audit = load_jsonl(audit_path)
audit_by = {a['attachment_node_id']: a for a in audit}
manifest = load_jsonl(manifest_path)
manifest_by = {m.get('fast_node_id') or m.get('attachment_node_id'): m for m in manifest}
nodes = load_jsonl(nodes_path)
nodes_by = {n['fast_node_id']: n for n in nodes}
intake = load_jsonl(intake_path)
intake_by = {i['fast_node_id']: i for i in intake}

accepted = []
for nid, w in WEB.items():
    a = audit_by.get(nid)
    if not a:
        continue
    a['decision'] = w['decision']
    a['reason_code'] = w['reason_code']
    a['reason'] = w['reason']
    if w['decision'] == 'ACCEPTED':
        a['retrieval_status'] = 'RETRIEVED_WEBFETCH'
        a['fact_status'] = 'VERIFIED'
        a['evidence_quote'] = w['evidence_quote']
        a['first_public_at_verification'] = w['fpa']
        a['occurred_at_verification'] = 'NOT_PROVEN_BY_PAGE'
        a['snapshot_path'] = w['snapshot']
        a['sha256'] = w['hash']
        # manifest
        if nid not in manifest_by:
            m = {
                'source_id': f"cand-{nid}",
                'event_id': a.get('attachment_event_id'),
                'fast_node_id': nid,
                'publisher': a.get('publisher'),
                'title': a.get('label', ''),
                'source_url': a.get('canonical_url') or a.get('source_url') or a.get('candidate_url'),
                'published_at': w['fpa'],
                'source_tier': a.get('source_tier', 'B'),
                'snapshot_path': w['snapshot'],
                'sha256': w['hash'],
                'snapshot_status': 'VERIFIED',
                'quote_verified': True,
                'quote_match_level': 'FULL_MATCH_WEBFETCH',
                'locator_type': 'html_text',
                'locator_value': w['evidence_quote'][:200],
                'is_duplicate_of_existing': False,
                'existing_evidence_id': None,
            }
            manifest.append(m)
            manifest_by[nid] = m
        # node upgrade
        node = nodes_by.get(nid)
        if node and node['evidence_status'] == 'PENDING_EVIDENCE':
            node['evidence_status'] = 'VERIFIED_EXISTING'
            sid = f"cand-{nid}"
            if sid not in node['source_ids']:
                node['source_ids'] = node['source_ids'] + [sid]
            if w['fpa'] and not node.get('first_public_at'):
                node['first_public_at'] = w['fpa']
            if node['visibility'] == 'UNRESOLVED':
                node['visibility'] = 'PUBLIC_PREDICTION'
            node['gap_reason'] = '来源已核验（WebFetch 确认官方页面与引用原文）；事件发生时刻待人工确认'
            node['promotion_eligible'] = False
            accepted.append(nid)

write_jsonl(audit_path, audit)
write_jsonl(manifest_path, manifest)
write_jsonl(nodes_path, nodes)

# ── Regenerate gap + validation reports ──
gap_path = os.path.join(WORK, "timeline_gap_report.json")
with open(gap_path, 'r', encoding='utf-8') as f:
    gap = json.load(f)
audit_by2 = {a['attachment_node_id']: a for a in audit}
gap['node_count'] = len(nodes)
gap['promotable_count'] = sum(1 for n in nodes if n.get('promotion_eligible'))
gap['pending_evidence_count'] = sum(1 for n in nodes if n['evidence_status'] == 'PENDING_EVIDENCE')
gap['candidate_accepted_count'] = sum(1 for a in audit if a['decision'] == 'ACCEPTED')
gap['candidate_rejected_count'] = sum(1 for a in audit if a['decision'] == 'REJECTED')
gap['candidate_needs_review_count'] = sum(1 for a in audit if a['decision'] == 'NEEDS_REVIEW')
for ev in gap['events']:
    eid = ev['event_id']
    ev_nodes = [n for n in nodes if n['event_id'] == eid]
    ev['verified_existing'] = sum(1 for n in ev_nodes if n['evidence_status'] == 'VERIFIED_EXISTING')
    ev['pending_evidence'] = sum(1 for n in ev_nodes if n['evidence_status'] == 'PENDING_EVIDENCE')
    ev['unresolved_time'] = sum(1 for n in ev_nodes if not n.get('occurred_at'))
    ev['public_prediction'] = sum(1 for n in ev_nodes if n.get('visibility') == 'PUBLIC_PREDICTION')
    ev['hidden_validation'] = sum(1 for n in ev_nodes if n.get('visibility') == 'HIDDEN_VALIDATION')
    ev['unresolved_visibility'] = sum(1 for n in ev_nodes if n.get('visibility') == 'UNRESOLVED')
    ev['promotable'] = sum(1 for n in ev_nodes if n.get('promotion_eligible'))
    ev['gaps'] = [{
        'fast_node_id': n['fast_node_id'],
        'evidence_status': n['evidence_status'],
        'phase': n.get('phase'),
        'research_task': n.get('fact', ''),
        'required_source': n.get('gap_reason') or '需要一手来源核验',
        'candidate_audit_result': audit_by2.get(n['fast_node_id'], {}).get('decision', 'N/A'),
        'candidate_rejection_reason': audit_by2.get(n['fast_node_id'], {}).get('reason'),
    } for n in ev_nodes if n['evidence_status'] == 'PENDING_EVIDENCE' or n.get('gap_reason')]
with open(gap_path, 'w', encoding='utf-8') as f:
    json.dump(gap, f, indent=2, ensure_ascii=False)

val_path = os.path.join(WORK, "validation_report.json")
with open(val_path, 'r', encoding='utf-8') as f:
    val = json.load(f)
val['node_count'] = len(nodes)
val['promotable_count'] = sum(1 for n in nodes if n.get('promotion_eligible'))
val['pending_evidence_count'] = sum(1 for n in nodes if n['evidence_status'] == 'PENDING_EVIDENCE')
val['unresolved_time_count'] = sum(1 for n in nodes if not n.get('occurred_at'))
val['candidate_intake_count'] = len(audit)
val['candidate_accepted_count'] = gap['candidate_accepted_count']
val['candidate_rejected_count'] = gap['candidate_rejected_count']
val['candidate_needs_review_count'] = gap['candidate_needs_review_count']
val['warnings'] = [
    f'UNRESOLVED_TIME:{val["unresolved_time_count"]}',
    f'PROVISIONAL_EXISTING_NOT_PROMOTABLE:{sum(1 for n in nodes if n["evidence_status"]=="VERIFIED_EXISTING" and not n.get("promotion_eligible"))}',
    'FAST_EPISODES_ARE_WORKBOOK_RECORDS_NOT_PRODUCTION_EPISODE_SCHEMA',
    f'CANDIDATE_SOURCES_REJECTED:{val["candidate_rejected_count"]}',
    f'CANDIDATE_SOURCES_NEEDS_REVIEW:{val["candidate_needs_review_count"]}',
]
with open(val_path, 'w', encoding='utf-8') as f:
    json.dump(val, f, indent=2, ensure_ascii=False)

print("WebFetch outcomes applied:")
print(f"  Upgraded to ACCEPTED: {accepted}")
print(f"  Marked NEEDS_REVIEW with reason: {[k for k,w in WEB.items() if w['decision']=='NEEDS_REVIEW']}")
print(f"\nFinal counts:")
print(f"  VERIFIED_EXISTING: {sum(1 for n in nodes if n['evidence_status']=='VERIFIED_EXISTING')}")
print(f"  PENDING_EVIDENCE:  {sum(1 for n in nodes if n['evidence_status']=='PENDING_EVIDENCE')}")
print(f"  Promotable:        {sum(1 for n in nodes if n.get('promotion_eligible'))}")
print(f"  Candidate ACCEPTED: {gap['candidate_accepted_count']}")
print(f"  Candidate REJECTED: {gap['candidate_rejected_count']}")
print(f"  Candidate NEEDS_REVIEW: {gap['candidate_needs_review_count']}")
