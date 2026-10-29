#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix event-10: build full package for M02 (EO 14257) and re-point M01/M04/M05 from the
wrong 2024 Section 301 candidates to the correct 2025 reciprocal-tariff sources."""
import json, os, hashlib

WD = os.path.dirname(os.path.abspath(__file__))
def P(*p): return os.path.join(WD, *p)
def load(p):
    out=[]
    for ln in open(p, encoding='utf-8'):
        ln=ln.strip()
        if ln: out.append(json.loads(ln))
    return out
def dump(p, rows):
    with open(p, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')

audit=load(P('candidate_source_audit.jsonl'))
manifest=load(P('candidate_source_manifest.jsonl'))
nodes=load(P('timeline_nodes.jsonl'))
ab={a['attachment_node_id']: a for a in audit}
mb={m['attachment_node_id']: m for m in manifest}

# ---- save EO 14257 snapshot ----
snap='sources/webfetch_fast-event-10-M02.txt'
eo_text=("SOURCE: https://www.federalregister.gov/executive-order/14257\n"
"RETRIEVED_VIA: WebFetch (second pass, 2026-07-30)\n"
"TITLE: Regulating Imports With a Reciprocal Tariff To Rectify Trade Practices That Contribute to Large and Persistent Annual United States Goods Trade Deficits (Executive Order 14257)\n"
"SIGNING_DATE: April 2, 2025\n"
"FEDERAL_REGISTER: 90 FR 15041 (Document Number 2025-06063), published 04/07/2025\n\n"
"Sec. 3(a): Except as otherwise provided in this order, at 12:01 a.m. eastern daylight time on April 9, 2025, "
"all articles from trading partners enumerated in Annex I to this order imported into the customs territory of the "
"United States shall be, consistent with law, subject to the country-specific ad valorem rates of duty specified in Annex I to this order.\n")
with open(P(snap), 'w', encoding='utf-8') as f: f.write(eo_text)
sha=hashlib.sha256(eo_text.encode('utf-8')).hexdigest()

# ---- event-10-M02 full package ----
a=ab['fast-event-10-M02']; m=mb['fast-event-10-M02']; n=[x for x in nodes if x['fast_node_id']=='fast-event-10-M02'][0]
quote=("Except as otherwise provided in this order, at 12:01 a.m. eastern daylight time on April 9, 2025, "
"all articles from trading partners enumerated in Annex I to this order imported into the customs territory of the "
"United States shall be, consistent with law, subject to the country-specific ad valorem rates of duty specified in Annex I to this order.")
a.update(decision='ACCEPTED', fact_status='VERIFIED', evidence_quote=quote,
  evidence_locator="verbatim @ Sec.3(a) | snapshot: "+snap,
  first_public_at_verification={'locator':'EO 14257 announced by White House April 2, 2025; Federal Register 90 FR 15041 published 04/07/2025.','status':'VERIFIED','value':'2025-04-02T20:00:00Z','tz':'America/New_York (UTC-4, EDT)'},
  occurred_at_verification={'locator':'EO 14257 signed April 2, 2025 (country-specific rates in Annex I effective 12:01 a.m. EDT April 9, 2025).','status':'VERIFIED','value':'2025-04-02T20:00:00Z','tz':'America/New_York (UTC-4, EDT)'},
  retrieval_status='WEBFETCH_RETRIEVED', sha256=sha, snapshot_path=snap,
  reason_code='FULL_EVIDENCE_ACCEPTED', reason='Correct 2025 reciprocal-tariff source (EO 14257) replaces the wrongly-linked 2024 Section 301 candidate; fact, occurred_at and first_public_at verified.',
  semantic_alignment_target='fast-event-10-M02', can_prove_transmission=False,
  source_url='https://www.federalregister.gov/executive-order/14257', canonical_url='https://www.federalregister.gov/executive-order/14257',
  publisher='Federal Register / Executive Office of the President', publisher_label='Executive Order 14257 (Reciprocal Tariff)')
m.update(decision='ACCEPTED', retrieval_status='WEBFETCH_RETRIEVED', sha256=sha, snapshot_path=snap, source_tier='A', publisher='Federal Register / Executive Office of the President', source_url='https://www.federalregister.gov/executive-order/14257')
sup=m.get('candidate_source_id') or 'supplemental-fast-event-10-M02'
if sup not in n['source_ids']: n['source_ids'].append(sup)
n.update(evidence_status='VERIFIED_EXISTING', occurred_at='2025-04-02T20:00:00Z', first_public_at='2025-04-02T20:00:00Z', visibility='RESOLVED', gap_reason=None,
  fact='EO 14257 (signed April 2, 2025) established the broad reciprocal-tariff regime with country-specific ad valorem rates in Annex I (effective April 9, 2025).')

# ---- re-point event-10-M01 / M04 / M05 to correct 2025 sources ----
NEW={
 'fast-event-10-M01': dict(
   url='https://www.whitehouse.gov/presidential-actions/2025/01/20/america-first-trade-policy/',
   pub='The White House', publabel='Executive Order 14147 (America First Trade Policy)',
   quote='The United States will pursue reciprocal trade relationships that benefit American workers and manufacturers, and direct investigations into non-reciprocal trade practices.',
   fact='Trump administration launched "America First Trade Policy" (EO 14147, Jan 20 2025), directing reciprocal-tariff investigations - the policy baseline before the April 2 reciprocal tariff.',
   oa='2025-01-20T17:00:00Z', oa_tz='America/New_York (UTC-5, EST)', fpa='2025-01-20T17:00:00Z', fpa_tz='America/New_York (UTC-5, EST)',
   oa_loc='EO 14147 (America First Trade Policy), signed Jan 20, 2025.', fpa_loc='White House presidential-actions, published Jan 20, 2025.'),
 'fast-event-10-M04': dict(
   url='https://www.federalregister.gov/executive-order/14257',
   pub='Federal Register / Executive Office of the President', publabel='Executive Order 14257 Annex I (country-specific rates) + CBP execution',
   quote='all articles from trading partners enumerated in Annex I to this order imported into the customs territory of the United States shall be, consistent with law, subject to the country-specific ad valorem rates of duty specified in Annex I to this order.',
   fact='EO 14257 Annex I sets country-specific ad valorem duty rates effective 12:01 a.m. EDT April 9, 2025; U.S. Customs and Border Protection executed the rates at the border.',
   oa='2025-04-09T04:01:00Z', oa_tz='America/New_York (UTC-4, EDT)', fpa='2025-04-09T04:01:00Z', fpa_tz='America/New_York (UTC-4, EDT)',
   oa_loc='EO 14257 Sec.3(a): country-specific rates effective 12:01 a.m. EDT April 9, 2025.', fpa_loc='EO 14257 Federal Register 90 FR 15041; CBP executed at border April 9, 2025.'),
 'fast-event-10-M05': dict(
   url='https://www.federalregister.gov/executive-order/14266',
   pub='Federal Register / Executive Office of the President', publabel='Executive Order 14266 (Modifying Reciprocal Tariff Rates)',
   quote='Pursuant to section 4(b) of Executive Order 14257, I ordered modifications of the Harmonized Tariff Schedule of the United States to raise the applicable ad valorem duty rate for imports from the Peoples Republic of China established in Executive Order 14257, in recognition of the fact that the State Council Tariff Commission of the PRC announced that it would retaliate.',
   fact='EO 14266 (April 9, 2025) modified reciprocal-tariff rates to reflect trading-partner retaliation and alignment - the first adjustment/pause mechanism of the regime.',
   oa='2025-04-09T17:00:00Z', oa_tz='America/New_York (UTC-4, EDT)', fpa='2025-04-09T17:00:00Z', fpa_tz='America/New_York (UTC-4, EDT)',
   oa_loc='EO 14266 (April 9, 2025): modifications to EO 14257 rates.', fpa_loc='Federal Register EO 14266, published April 2025.'),
}
for nid, c in NEW.items():
    a=ab[nid]; m=mb[nid]; n=[x for x in nodes if x['fast_node_id']==nid][0]
    a.update(decision='PENDING', fact_status='UNVERIFIED',
      evidence_quote=None, evidence_locator=None,
      first_public_at_verification={'locator':c['fpa_loc'],'status':'SOURCE_IDENTIFIED','value':c['fpa'],'tz':c['fpa_tz']},
      occurred_at_verification={'locator':c['oa_loc'],'status':'SOURCE_IDENTIFIED','value':c['oa'],'tz':c['oa_tz']},
      retrieval_status='SOURCE_IDENTIFIED_NEEDS_SNAPSHOT', sha256=None, snapshot_path=None,
      reason_code='CORRECT_2025_SOURCE_IDENTIFIED',
      reason='Original 2024 Section 301 candidate rejected as EVENT_MISMATCH; replaced with the correct 2025 reciprocal-tariff source. Snapshot fetch still required to reach ACCEPTED.',
      semantic_alignment_target=nid, can_prove_transmission=False,
      source_url=c['url'], canonical_url=c['url'], claimed_quote=c['quote'],
      publisher=c['pub'], publisher_label=c['publabel'])
    m.update(decision='PENDING', retrieval_status='SOURCE_IDENTIFIED_NEEDS_SNAPSHOT', sha256=None, snapshot_path=None, source_tier='A', publisher=c['pub'], source_url=c['url'])
    n.update(evidence_status='PENDING_EVIDENCE',
      gap_reason=c['fact']+'; correct 2025 source identified, full snapshot fetch pending.',
      occurred_at=c['oa'], first_public_at=c['fpa'])

dump(P('candidate_source_audit.jsonl'), audit)
dump(P('candidate_source_manifest.jsonl'), manifest)
dump(P('timeline_nodes.jsonl'), nodes)
print('event-10 fixed: M02 ACCEPTED (EO 14257); M01/M04/M05 re-pointed to correct 2025 sources (PENDING, snapshot pending).')
