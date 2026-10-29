#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Annotate the 12 WebFetch second-pass nodes with their outcome (all blocked/404).
Keeps the audit trail self-contained: BOTH urllib (local snapshot) and WebFetch failed,
so the SOURCE_UNREACHABLE verdict is independently corroborated."""
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
# node -> observed WebFetch outcome (2026-07-30 second pass)
WEB2={
 'fast-event-01-M03':'404 (URL moved)',
 'fast-event-02-M03':'404 (White House retired the page)',
 'fast-event-05-M03':'404 (FINMA retired the page)',
 'fast-event-05-M04':'No press release with selected ID (admin.ch)',
 'fast-event-06-M01':'Cloudflare "Just a moment" block (IEA)',
 'fast-event-06-M03':'Page redirected to current content; 2023 cut notice gone (OPEC)',
 'fast-event-07-M01':'404 (UN retired the page)',
 'fast-event-07-M02':'Cloudflare block (gov.il)',
 'fast-event-07-M03':'"Coming Soon" empty page (IMO)',
 'fast-event-07-M05':'404 (White House retired the page)',
 'fast-event-08-M04':'404 (BOJ PDF URL changed)',
 'fast-event-08-M05':'404 (JPX retired the page)',
}
n=0
for a in audit:
    nid=a.get('attachment_node_id')
    if nid in WEB2:
        a['web_fetch_second_pass']={'date':'2026-07-30','status':'FAILED','detail':WEB2[nid]}
        if a.get('decision')=='PENDING':
            a['reason']=(a.get('reason') or '') + f" WebFetch second-pass also failed: {WEB2[nid]}."
        n+=1
save_jsonl(P('candidate_source_audit.jsonl'),audit)
print(f"Annotated {n} rows with WebFetch second-pass outcomes.")
