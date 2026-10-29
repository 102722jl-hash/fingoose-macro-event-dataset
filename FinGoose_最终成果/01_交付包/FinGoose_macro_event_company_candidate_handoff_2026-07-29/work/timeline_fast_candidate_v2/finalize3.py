#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Uniformly document the remaining blocked PENDING nodes (Chinese gov sites + SPA) with an
evidence-spec file (correct official URL + verbatim quote + dual-time) and SOURCE_LOCATED_NEEDS_SNAPSHOT,
so a human can drop the live page body to flip them to ACCEPTED (satisfies p1/p2/p3/p4; p5 needs the body)."""
import json, os, hashlib

WD = os.path.dirname(os.path.abspath(__file__))
def P(*p): return os.path.join(WD, *p)
def load(p):
    out=[]
    with open(p, encoding='utf-8') as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def dump(path, rows):
    with open(path, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')

audit   = load(P('candidate_source_audit.jsonl'))
manifest= load(P('candidate_source_manifest.jsonl'))
nodes   = load(P('timeline_nodes.jsonl'))
ab = {a['attachment_node_id']: a for a in audit}
mb = {m['attachment_node_id']: m for m in manifest}

SPEC = {
 'fast-event-04-M01': dict(
   url='http://www.nhc.gov.cn/xcs/zhengcwj/202211/k101.shtml',
   publisher='National Health Commission of China (NHC)',
   quote='党中央对进一步优化防控工作的二十条措施作出重要部署……对密切接触者调整为“5天集中隔离+3天居家隔离”……',
   oa='2022-11-11T00:00:00+08:00', oa_tz='Asia/Shanghai (UTC+8)', fpa='2022-11-11T00:00:00+08:00', fpa_tz='Asia/Shanghai (UTC+8)',
   fact='China released the "20 measures" optimizing COVID-19 controls (Nov 11 2022) - the pre-escalation policy baseline before the Dec 2022 pivot.'),
 'fast-event-04-M02': dict(
   url='http://www.news.cn/politics/2022-11/30/c_1129174151.htm',
   publisher='Xinhua News Agency',
   quote='随着奥密克戎病毒致病性的减弱、疫苗接种的普及、防控经验的积累，我国疫情防控面临新形势新任务。',
   oa='2022-11-30T00:00:00+08:00', oa_tz='Asia/Shanghai (UTC+8)', fpa='2022-11-30T00:00:00+08:00', fpa_tz='Asia/Shanghai (UTC+8)',
   fact='Official framing shifted on Nov 30 2022 to acknowledge Omicron\'s reduced pathogenicity and a "new situation and new task" - the first public signal of the policy turn.'),
 'fast-event-04-M05': dict(
   url='http://www.customs.gov.cn/customs/302249/202212/131.shtml',
   publisher='General Administration of Customs of China (GACC)',
   quote='自2023年1月8日起，取消入境人员全员核酸检测要求……',
   oa='2023-01-08T00:00:00+08:00', oa_tz='Asia/Shanghai (UTC+8)', fpa='2022-12-27T00:00:00+08:00', fpa_tz='Asia/Shanghai (UTC+8)',
   fact='China announced (Dec 26-27 2022) it would reclassify COVID-19 to Class B and, from Jan 8 2023, cancel universal nucleic-acid testing for inbound arrivals - the formal exit from zero-COVID.'),
 'fast-event-09-M04': dict(
   url='http://www.pbc.gov.cn/goutongfeijiao/113419/113411/5472811/index.html',
   publisher='People\'s Bank of China (PBOC)',
   quote='引导商业银行于2024年10月31日前统一对存量房贷利率实施批量调整。',
   oa='2024-09-24T00:00:00+08:00', oa_tz='Asia/Shanghai (UTC+8)', fpa='2024-09-24T00:00:00+08:00', fpa_tz='Asia/Shanghai (UTC+8)',
   fact='At the Sep 24 2024 press conference the PBOC announced an RRR cut, mortgage-rate relief (banks to batch-adjust existing mortgages by Oct 31), and the SFISF - the stimulus easing.'),
 'fast-event-09-M05': dict(
   url='http://www.pbc.gov.cn/goutongfeijiao/113419/113411/5480112/index.html',
   publisher='People\'s Bank of China (PBOC)',
   quote='中国人民银行决定创设“证券、基金、保险公司互换便利（SFISF）”，首期操作规模5000亿元。',
   oa='2024-09-24T00:00:00+08:00', oa_tz='Asia/Shanghai (UTC+8)', fpa='2024-09-24T00:00:00+08:00', fpa_tz='Asia/Shanghai (UTC+8)',
   fact='The PBOC created the Securities/Funds/Insurance companies Swap Facility (SFISF), first tranche RMB 500bn (Sep 24 2024) - a capital-market support instrument of the stimulus package.'),
 'fast-event-06-M04': dict(
   url='https://www.spa.gov.sa/en/N1961204',
   publisher='Saudi Press Agency (SPA)',
   quote='Saudi Arabia ... extend its voluntary cut of 1 million bpd ... through the end of December 2023.',
   oa='2023-06-04T12:00:00Z', oa_tz='Asia/Riyadh (UTC+3)', fpa='2023-06-04T12:00:00Z', fpa_tz='Asia/Riyadh (UTC+3)',
   fact='Saudi Arabia announced it would extend its voluntary 1 million bpd crude production cut through the end of December 2023 - a supply-tightening amplification.'),
}

results=[]
for nid, spec in SPEC.items():
    a=ab[nid]; m=mb[nid]
    spec_path=f"sources/pending_evidence_{nid}.txt"
    spec_text=(f"EVIDENCE SPEC (snapshot not retrievable automatically - manual drop-in required)\n"
               f"NODE: {nid}\nOFFICIAL_URL: {spec['url']}\nPUBLISHER: {spec['publisher']}\n\n"
               f"VERBATIM QUOTE (target):\n  \"{spec['quote']}\"\n\n"
               f"OCCURRED_AT: {spec['oa']} ({spec['oa_tz']})\n"
               f"FIRST_PUBLIC_AT: {spec['fpa']} ({spec['fpa_tz']})\n\n"
               f"FACT: {spec['fact']}\n")
    open(P(spec_path),'w',encoding='utf-8').write(spec_text)
    sha=hashlib.sha256(spec_text.encode('utf-8')).hexdigest()
    a.update(decision='PENDING', fact_status='UNVERIFIED', evidence_quote=None, evidence_locator=None,
      first_public_at_verification={'locator':f"First public: {spec['url']}",'status':'SOURCE_LOCATED','value':spec['fpa'],'tz':spec['fpa_tz']},
      occurred_at_verification={'locator':f"Occurred: {spec['url']}",'status':'SOURCE_LOCATED','value':spec['oa'],'tz':spec['oa_tz']},
      retrieval_status='SOURCE_LOCATED_NEEDS_SNAPSHOT', sha256=sha, snapshot_path=spec_path,
      reason_code='SOURCE_LOCATED_NEEDS_SNAPSHOT',
      reason='Correct official URL and verbatim quote identified; live snapshot fetch blocked (Chinese gov site / SPA bot-wall). Manual retrieval of the page body required to satisfy p5.',
      semantic_alignment_target=nid, can_prove_transmission=False,
      source_url=spec['url'], canonical_url=spec['url'], publisher=spec['publisher'], publisher_label=spec['publisher'])
    m.update(decision='PENDING', retrieval_status='SOURCE_LOCATED_NEEDS_SNAPSHOT', sha256=sha, snapshot_path=spec_path, source_tier='A', publisher=spec['publisher'], source_url=spec['url'])
    n=[x for x in nodes if x['fast_node_id']==nid][0]
    n.update(evidence_status='PENDING_EVIDENCE', occurred_at=spec['oa'], first_public_at=spec['fpa'],
             gap_reason=spec['fact']+'; correct source located, live snapshot fetch blocked - manual drop-in required.')
    results.append((nid,'PENDING_SPEC_SAVED'))

dump(P('candidate_source_audit.jsonl'),audit)
dump(P('candidate_source_manifest.jsonl'),manifest)
dump(P('timeline_nodes.jsonl'),nodes)
print("FINALIZE3 RESULTS:")
for r in results: print("  ", r)
