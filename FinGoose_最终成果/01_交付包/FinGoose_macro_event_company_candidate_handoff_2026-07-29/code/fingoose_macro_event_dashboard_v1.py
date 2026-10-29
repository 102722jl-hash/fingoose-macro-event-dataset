from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

MARKET_REQUIRED_FILES = ('summary.json','event_dossiers.jsonl','market_windows.jsonl','attribution_samples.jsonl','training_projection.jsonl','hidden_forecast_outcomes.jsonl','hidden_attribution_labels.jsonl','review_records.jsonl','source_manifest.jsonl')
REQUIRED_FILES = MARKET_REQUIRED_FILES
COMPANY_REQUIRED_FILES = ('summary.json','company_event_dossiers.jsonl','company_metric_facts.jsonl','company_stock_windows.jsonl','company_attribution_samples.jsonl','company_forecast_samples.jsonl','company_candidate_training_projection.jsonl','company_candidate_hidden_labels.jsonl','company_hidden_outcomes.jsonl','company_review_records.jsonl','company_evidence_gaps.jsonl','candidate_company_registry.jsonl','source_manifest.jsonl','rejected.jsonl','validation_report.json')


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open('r', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    result: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get(key) is not None:
            result[str(row[key])].append(row)
    return dict(result)


def _one(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key) is not None}


class MacroEventDashboardRepository:
    def __init__(self, output_root: Path, company_output_root: Path | None = None) -> None:
        self.output_root = Path(output_root)
        p = {name: self.output_root / name for name in MARKET_REQUIRED_FILES}
        for name, path in p.items():
            if not path.is_file():
                raise FileNotFoundError(f'Required dashboard artifact is missing: {name}')
        self.persisted_summary = json.loads(p['summary.json'].read_text(encoding='utf-8-sig'))
        self.event_dossiers = _read_jsonl(p['event_dossiers.jsonl'])
        self.market_windows = _read_jsonl(p['market_windows.jsonl'])
        self.attribution_samples = _read_jsonl(p['attribution_samples.jsonl'])
        self.training_projection = _read_jsonl(p['training_projection.jsonl'])
        self.hidden_forecast_outcomes = _read_jsonl(p['hidden_forecast_outcomes.jsonl'])
        self.hidden_attribution_labels = _read_jsonl(p['hidden_attribution_labels.jsonl'])
        self.review_records = _read_jsonl(p['review_records.jsonl'])
        self.source_manifest = _read_jsonl(p['source_manifest.jsonl'])
        self.events_by_id = _one(self.event_dossiers, 'event_id')
        self.samples_by_id = _one(self.attribution_samples, 'record_id')
        self.reviews_by_id = _one(self.review_records, 'review_id')
        self.market_windows_by_id = _one(self.market_windows, 'market_window_id')
        self.training_projection_by_id = _one(self.training_projection, 'record_id')
        self.hidden_labels_by_record_id = _one(self.hidden_attribution_labels, 'record_id')
        self.hidden_outcomes_by_record_id = {str(r.get('record_id',r.get('source_sample_id'))):r for r in self.hidden_forecast_outcomes}
        self.sources_by_id = _one(self.source_manifest, 'source_id')
        self.market_windows_by_event_id = _group(self.market_windows, 'event_id')
        self.samples_by_event_id = _group(self.attribution_samples, 'event_id')
        self.sources_by_event_id = _group(self.source_manifest, 'event_id')
        self.company_output_root = Path(company_output_root) if company_output_root else None
        names = ('company_dossiers','company_metric_facts','company_stock_windows','company_attribution_samples','company_forecast_samples','company_reviews','company_gaps','company_sources')
        for name in names:
            setattr(self, name, [])
        self.company_summary: dict[str, Any] = {}
        if self.company_output_root:
            cp = {name:self.company_output_root/name for name in COMPANY_REQUIRED_FILES}
            for name,path in cp.items():
                if not path.is_file():
                    raise FileNotFoundError(f'Required company dashboard artifact is missing: {name}')
            self.company_summary = json.loads(cp['summary.json'].read_text(encoding='utf-8-sig'))
            self.company_dossiers = _read_jsonl(cp['company_event_dossiers.jsonl'])
            self.company_metric_facts = _read_jsonl(cp['company_metric_facts.jsonl'])
            self.company_stock_windows = _read_jsonl(cp['company_stock_windows.jsonl'])
            self.company_attribution_samples = _read_jsonl(cp['company_attribution_samples.jsonl'])
            self.company_forecast_samples = _read_jsonl(cp['company_forecast_samples.jsonl'])
            self.company_reviews = _read_jsonl(cp['company_review_records.jsonl'])
            self.company_gaps = _read_jsonl(cp['company_evidence_gaps.jsonl'])
            self.company_sources = _read_jsonl(cp['source_manifest.jsonl'])
        self.company_dossiers_by_id = _one(self.company_dossiers,'dossier_id')
        self.company_dossiers_by_event = _group(self.company_dossiers,'event_id')
        self.company_facts_by_dossier = _group(self.company_metric_facts,'dossier_id')
        self.company_windows_by_dossier = _one(self.company_stock_windows,'dossier_id')
        self.company_attribution_by_dossier = _one(self.company_attribution_samples,'dossier_id')
        self.company_forecast_by_dossier = _one(self.company_forecast_samples,'dossier_id')
        self.company_review_by_dossier = _one(self.company_reviews,'dossier_id')
        self.company_gaps_by_dossier = _group(self.company_gaps,'dossier_id')
        self.company_sources_by_id = _one(self.company_sources,'source_id')

    def overview(self) -> dict[str, Any]:
        labels = Counter(r.get('label') for r in self.hidden_attribution_labels if r.get('label'))
        years = Counter(str(r.get('occurred_at',''))[:4] for r in self.event_dossiers if r.get('occurred_at'))
        categories = Counter(r.get('category') for r in self.event_dossiers if r.get('category'))
        second = sum(isinstance(r.get('second_review'),dict) and r['second_review'].get('status') in {'APPROVED','COMPLETED'} for r in self.review_records)
        adjudications = sum(isinstance(r.get('adjudication'),dict) and r['adjudication'].get('status') in {'APPROVED','COMPLETED'} for r in self.review_records)
        return {'persisted':deepcopy(self.persisted_summary),'computed':{'event_count':len(self.event_dossiers),'sample_count':len(self.attribution_samples),'market_window_count':len(self.market_windows),'completed_second_reviews':second,'completed_adjudications':adjudications},'company':deepcopy(self.company_summary),'label_distribution':dict(sorted(labels.items())),'year_distribution':dict(sorted(years.items())),'category_distribution':dict(sorted(categories.items())),'reasoning_chain_sequence':deepcopy(self.persisted_summary.get('forecast_reasoning_chain',[]))}

    def list_events(self) -> list[dict[str, Any]]:
        return [{**deepcopy(r),'market_sample_count':len(self.samples_by_event_id.get(r['event_id'],[])),'company_dossier_count':len(self.company_dossiers_by_event.get(r['event_id'],[]))} for r in self.event_dossiers]

    def event_detail(self, event_id: str) -> dict[str, Any]:
        if event_id not in self.events_by_id: raise KeyError(event_id)
        samples=[]
        for row in self.samples_by_event_id.get(event_id,[]):
            item=deepcopy(row)
            item['market_windows']=[deepcopy(self.market_windows_by_id[x]) for x in row.get('market_window_ids',[]) if x in self.market_windows_by_id]
            item['hidden_label']=deepcopy(self.hidden_labels_by_record_id.get(row['record_id']))
            samples.append(item)
        return {'event':deepcopy(self.events_by_id[event_id]),'market_samples':samples,'market_windows':deepcopy(self.market_windows_by_event_id.get(event_id,[])),'company_dossiers':[self._company_row(x) for x in self.company_dossiers_by_event.get(event_id,[])],'sources':deepcopy(self.sources_by_event_id.get(event_id,[]))}

    def _company_row(self, dossier: dict[str, Any]) -> dict[str, Any]:
        did=dossier['dossier_id']; a=self.company_attribution_by_dossier.get(did,{}); r=self.company_review_by_dossier.get(did,{})
        association = a.get('association', 'PENDING_ASSESSMENT')
        if a.get('label_status') == 'PENDING_EVIDENCE' and str(self.company_summary.get('dataset_version','')).startswith('fingoose-macro-event-company-enriched-candidate'):
            association = 'PENDING_ASSESSMENT'
        return {'dossier_id':did,'event_id':dossier['event_id'],'company_code':dossier['company_code'],'company_name':dossier['company_name'],'industry':dossier.get('industry','UNKNOWN'),'association':association,'direction':a.get('direction','UNCERTAIN'),'confidence':a.get('confidence',dossier.get('confidence','LOW')),'evidence_status':dossier.get('evidence_status',dossier.get('candidate_status','PENDING_EVIDENCE')),'review_status':r.get('review_status',dossier.get('review_status','PENDING_EVIDENCE'))}


    def list_companies(self, *, event_id: str='', company_query: str='', association: str='', direction: str='', evidence_status: str='', review_status: str='') -> list[dict[str, Any]]:
        q=company_query.casefold().strip()
        return [r for r in map(self._company_row,self.company_dossiers) if (not event_id or r['event_id']==event_id) and (not q or q in r['company_code'].casefold() or q in r['company_name'].casefold()) and (not association or r['association']==association) and (not direction or r['direction']==direction) and (not evidence_status or r['evidence_status']==evidence_status) and (not review_status or r['review_status']==review_status)]

    def company_detail(self, dossier_id: str) -> dict[str, Any]:
        if dossier_id not in self.company_dossiers_by_id: raise KeyError(dossier_id)
        dossier=deepcopy(self.company_dossiers_by_id[dossier_id]); ids=set(dossier.get('event_source_ids',[]))
        for node in dossier.get('transmission_chain',{}).get('nodes',[]): ids.update(x.get('source_id') for x in node.get('evidence_refs',[]) if x.get('source_id'))
        sources=[]
        for sid in sorted(ids):
            source=self.company_sources_by_id.get(sid) or self.sources_by_id.get(sid)
            if source:
                item=deepcopy(source); item.setdefault('source_locator',deepcopy(item.get('locator'))); item.setdefault('verification_status','VERIFIED'); item.setdefault('model_visible',True); sources.append(item)
        attribution = deepcopy(self.company_attribution_by_dossier.get(dossier_id,{}))
        if attribution.get('label_status') == 'PENDING_EVIDENCE' and str(self.company_summary.get('dataset_version','')).startswith('fingoose-macro-event-company-enriched-candidate'):
            attribution['association'] = 'PENDING_ASSESSMENT'
        return {'dossier':dossier,'metric_facts':deepcopy(self.company_facts_by_dossier.get(dossier_id,[])),'stock_window':deepcopy(self.company_windows_by_dossier.get(dossier_id,{})),'attribution_sample':attribution,'forecast_sample':deepcopy(self.company_forecast_by_dossier.get(dossier_id,{})),'evidence_gaps':deepcopy(self.company_gaps_by_dossier.get(dossier_id,[])),'review':deepcopy(self.company_review_by_dossier.get(dossier_id,{})),'sources':sources}

    def list_reviews(self) -> list[dict[str, Any]]:
        return [{'domain':'MARKET',**deepcopy(r)} for r in self.review_records]+[{'domain':'COMPANY',**deepcopy(r)} for r in self.company_reviews]


HTML_PATH = Path(__file__).with_name('fingoose_macro_event_dashboard_v1.html')
INDEX_HTML = HTML_PATH.read_text(encoding='utf-8') if HTML_PATH.is_file() else '<!doctype html><title>FinGoose dashboard unavailable</title>'


def make_handler(repository: MacroEventDashboardRepository) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def send(self,status:int,payload:Any,kind:str='application/json; charset=utf-8')->None:
            body=payload.encode('utf-8') if isinstance(payload,str) else json.dumps(payload,ensure_ascii=False).encode('utf-8'); self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
        def do_GET(self)->None:
            p=urlparse(self.path); path=unquote(p.path); q=parse_qs(p.query); first=lambda n:q.get(n,[''])[0]
            try:
                if path=='/': self.send(200,INDEX_HTML,'text/html; charset=utf-8')
                elif path=='/api/overview': self.send(200,repository.overview())
                elif path=='/api/events': self.send(200,repository.list_events())
                elif path.startswith('/api/event/'): self.send(200,repository.event_detail(path.removeprefix('/api/event/')))
                elif path=='/api/companies': self.send(200,repository.list_companies(event_id=first('event_id'),company_query=first('company'),association=first('association'),direction=first('direction'),evidence_status=first('evidence_status'),review_status=first('review_status')))
                elif path.startswith('/api/company/'): self.send(200,repository.company_detail(path.removeprefix('/api/company/')))
                elif path=='/api/reviews': self.send(200,repository.list_reviews())
                else: self.send(404,{'error':'NOT_FOUND'})
            except KeyError as exc: self.send(404,{'error':'NOT_FOUND','id':str(exc.args[0])})
        def log_message(self,format:str,*args:Any)->None: return
    return Handler


def main()->int:
    root=Path(__file__).resolve().parent; parser=argparse.ArgumentParser(description='Serve the FinGoose unified read-only dashboard.')
    parser.add_argument('--market-output-root','--output-root',dest='market_root',type=Path,default=root/'outputs'/'fingoose_macro_event_attribution_v1'); parser.add_argument('--company-output-root',type=Path,default=root/'outputs'/'fingoose_macro_event_company_official_enriched_candidate_v1'); parser.add_argument('--host',default='127.0.0.1'); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args()
    server=ThreadingHTTPServer((args.host,args.port),make_handler(MacroEventDashboardRepository(args.market_root,args.company_output_root))); print(f'FinGoose dashboard: http://{args.host}:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
    return 0


if __name__=='__main__': raise SystemExit(main())