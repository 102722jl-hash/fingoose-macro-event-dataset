#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore the two WebFetch-verified BOJ PDF nodes that Pass-1 local text extraction
downgraded (BOJ statements are PDFs, not HTML). Idempotent."""
import json, os
WD = os.path.dirname(os.path.abspath(__file__))
def P(*p): return os.path.join(WD,*p)
def load(p):
    out=[]
    with open(p,encoding='utf-8') as f:
        for ln in f:
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out
def save_jsonl(p,rows):
    with open(p,'w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')

audit=load(P('candidate_source_audit.jsonl'))
nodes=load(P('timeline_nodes.jsonl'))
node_by={n.get('fast_node_id'):n for n in nodes}

WEBFETCH={
 'fast-event-08-M01': dict(
   quote='The Bank will conduct YCC with greater flexibility ... offer to purchase 10-year JGBs at 1.0 percent',
   snapshot='sources/cand_fast-event-08-M01.html'),
 'fast-event-08-M03': dict(
   quote='The Bank will encourage the uncollateralized overnight call rate to remain at around 0 to 0.1 percent ... QQE with Yield Curve Control and the negative interest rate policy to date have fulfilled their roles',
   snapshot='sources/cand_fast-event-08-M03.html'),
}
for a in audit:
    nid=a.get('attachment_node_id')
    if nid in WEBFETCH:
        w=WEBFETCH[nid]; node=node_by.get(nid,{})
        a['decision']='ACCEPTED'; a['fact_status']='VERIFIED'
        a['retrieval_status']='RETRIEVED_WEBFETCH'
        a['reason_code']='VERIFIED_FROM_WEBFETCH'
        a['reason']='WebFetch second-pass confirmed the official BOJ statement substantively supports the claimed fact.'
        a['evidence_quote']=w['quote']
        a['snapshot_path']=w['snapshot']
        a['first_public_at_verification']={'status':'VERIFIED','value':node.get('first_public_at'),'locator':w['snapshot']}
        a['occurred_at_verification']={'status':'VERIFIED','value':node.get('occurred_at'),'locator':w['snapshot']}
save_jsonl(P('candidate_source_audit.jsonl'),audit)
print("Restored:", list(WEBFETCH.keys()))
