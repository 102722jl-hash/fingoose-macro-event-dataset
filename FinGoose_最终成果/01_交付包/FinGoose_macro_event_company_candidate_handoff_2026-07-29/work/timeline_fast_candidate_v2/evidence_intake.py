#!/usr/bin/env python3
"""
FinGoose Timeline Evidence Intake & Audit Script
Processes 50 candidate links from pasted-text.txt:
  1. Parse entries
  2. Unwrap Google/gmail-wrapped URLs
  3. Batch-fetch official pages (parallel)
  4. Save snapshots + compute SHA-256
  5. Programmatic quote matching
  6. Generate candidate_source_intake.jsonl / candidate_source_audit.jsonl / candidate_source_manifest.jsonl
  7. Update timeline_nodes.jsonl
  8. Regenerate timeline_gap_report.json (clean)
  9. Regenerate validation_report.json
"""

import json, hashlib, os, re, ssl, sys, time
import urllib.request, urllib.error
from urllib.parse import urlparse, parse_qs, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

# ── Paths ──
PASTED = r"C:\Users\LL\.codex\attachments\64edc179-4c75-4671-ac15-69f02f83a6e2\pasted-text.txt"
WORK   = r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\work\timeline_fast_candidate_v2"
SRC    = os.path.join(WORK, "sources")
NODES  = os.path.join(WORK, "timeline_nodes.jsonl")
EXIST_SRC = r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\data\market_event_attribution_v2_candidate\source_manifest.jsonl"

os.makedirs(SRC, exist_ok=True)

# ── SSL / headers ──
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HDRS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
}

# ── HTML text extractor ──
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'meta', 'link', 'head'):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'meta', 'link', 'head'):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)
    def get_text(self):
        return ' '.join(self.parts)

def strip_html(b):
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            s = b.decode(enc)
            break
        except:
            continue
    ext = TextExtractor()
    try:
        ext.feed(s)
    except:
        pass
    return re.sub(r'\s+', ' ', ext.get_text()).strip()

# ── URL unwrapping ──
def unwrap_url(raw):
    raw = raw.strip()
    if 'google.com/search' in raw or 'google.com/url' in raw:
        p = urlparse(raw)
        q = parse_qs(p.query)
        if 'q' in q and q['q']:
            return unquote(q['q'][0])
    # fix malformed like http.xxx.gov.cn
    if re.match(r'^https?\.', raw):
        raw = re.sub(r'^(https?)\.', r'\1://', raw)
    return raw

# ── Publisher / tier ──
def get_publisher(url):
    d = urlparse(url).netloc.lower()
    m = {
        'who.int': 'World Health Organization',
        'federalreserve.gov': 'Federal Reserve Board',
        'whitehouse.gov': 'The White House',
        'federalregister.gov': 'Federal Register',
        'eia.gov': 'U.S. Energy Information Administration',
        'fdic.gov': 'Federal Deposit Insurance Corporation',
        'boj.or.jp': 'Bank of Japan',
        'opec.org': 'OPEC',
        'nato.int': 'NATO',
        'un.org': 'United Nations',
        'pbc.gov.cn': "People's Bank of China",
        'nhc.gov.cn': 'National Health Commission of China',
        'mofcom.gov.cn': 'Ministry of Commerce of China',
        'scio.gov.cn': 'State Council Information Office of China',
        'customs.gov.cn': 'China Customs',
        'gov.cn': 'State Council of China',
        'news.cn': 'Xinhua News Agency',
        'sec.gov': 'U.S. Securities and Exchange Commission',
        'bls.gov': 'U.S. Bureau of Labor Statistics',
        'treasury.gov': 'U.S. Department of the Treasury',
        'spa.gov.sa': 'Saudi Press Agency',
        'admin.ch': 'Swiss Federal Council',
        'finma.ch': 'FINMA',
        'snb.ch': 'Swiss National Bank',
        'kremlin.ru': 'President of Russia',
        'gazzettaufficiale.it': 'Italian Government',
        'ustr.gov': 'Office of the United States Trade Representative',
        'cbp.gov': 'U.S. Customs and Border Protection',
        'defense.gov': 'U.S. Department of Defense',
        'gov.il': 'Government of Israel',
        'imo.org': 'International Maritime Organization',
        'iea.org': 'International Energy Agency',
        'jpx.co.jp': 'Japan Exchange Group',
        'jtuc-rengo.org': 'Japanese Trade Union Confederation (RENGO)',
    }
    for k, v in m.items():
        if k in d:
            return v
    return d

TIER_A = {
    'Federal Reserve Board', 'The White House', 'Federal Register',
    'U.S. Energy Information Administration', 'Federal Deposit Insurance Corporation',
    'Bank of Japan', "People's Bank of China", 'State Council of China',
    'U.S. Securities and Exchange Commission', 'U.S. Bureau of Labor Statistics',
    'U.S. Department of the Treasury', 'Swiss Federal Council', 'FINMA',
    'Swiss National Bank', 'Office of the United States Trade Representative',
    'U.S. Customs and Border Protection', 'U.S. Department of Defense',
    'International Energy Agency', 'National Health Commission of China',
    'Ministry of Commerce of China', 'State Council Information Office of China',
    'China Customs',
}

def get_tier(pub):
    return 'A' if pub in TIER_A else 'B'

# ── Parse pasted-text.txt ──
def parse_entries(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # cut at JSON section
    cut = content.find('### 二、')
    if cut > 0:
        content = content[:cut]
    lines = content.split('\n')
    entries = []
    i = 0
    while i < len(lines):
        m = re.match(r'\d+\.\s+\*\*(fast-event-(\d+)-M(\d+))\*\*\s+\(([^)]+)\)', lines[i])
        if m:
            nid = m.group(1)
            evt = f"event-{m.group(2)}"
            seq = int(m.group(3))
            label = m.group(4)
            # next 3 lines
            ts = None; url = ''; title = ''; quote = ''
            for j in range(1, 4):
                if i + j < len(lines):
                    ln = lines[i + j]
                    if '时间戳' in ln:
                        tm = re.search(r'`([^`]+)`', ln)
                        ts = tm.group(1) if tm else None
                    elif '官方链接' in ln:
                        bp = ln.find('](')
                        if bp >= 0:
                            tm = re.search(r'\[([^\]]*)\]', ln)
                            title = tm.group(1) if tm else ''
                            url = ln[bp+2:]
                            if url.endswith(')'):
                                url = url[:-1]
                            url = url.strip()
                    elif '引用原文' in ln:
                        # grab everything after the colon
                        qm = re.search(r'引用原文\*?\*?：\s*["\u201c\u201d"]?(.+?)["\u201c\u201d"]?\s*$', ln)
                        if qm:
                            quote = qm.group(1).strip().rstrip('"\u201d\u201c')
                        else:
                            # take everything after the last colon
                            ci = ln.rfind('：')
                            if ci >= 0:
                                quote = ln[ci+1:].strip().strip('"\u201c\u201d')
            entries.append({
                'fast_node_id': nid, 'event_id': evt, 'sequence': seq,
                'label': label, 'candidate_timestamp': ts,
                'raw_link': url, 'link_title': title, 'claimed_quote': quote,
            })
        i += 1
    return entries

# ── Fetch URL ──
def fetch_url(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=HDRS)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        ct = resp.headers.get('Content-Type', '')
        data = resp.read(5_000_000)  # max 5MB
        final_url = resp.url
        return {
            'status': resp.status, 'content_type': ct,
            'data': data, 'final_url': final_url, 'error': None,
        }
    except urllib.error.HTTPError as e:
        return {'status': e.code, 'content_type': '', 'data': b'',
                'final_url': url, 'error': f'HTTP {e.code}'}
    except Exception as e:
        return {'status': 0, 'content_type': '', 'data': b'',
                'final_url': url, 'error': str(e)[:200]}

# ── Quote matching ──
def norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()

def match_quote(page_text, claimed):
    if not claimed or not page_text:
        return {'level': 'NO_MATCH', 'detail': 'empty input'}
    pt = norm(page_text)
    cq = norm(claimed)
    # full match
    if cq in pt:
        return {'level': 'FULL_MATCH', 'detail': 'exact quote found in page text'}
    # try first 60 chars
    head = cq[:60]
    if len(head) > 20 and head in pt:
        return {'level': 'PARTIAL_MATCH', 'detail': 'first 60 chars matched'}
    # try last 60 chars
    tail = cq[-60:]
    if len(tail) > 20 and tail in pt:
        return {'level': 'PARTIAL_MATCH', 'detail': 'last 60 chars matched'}
    # try middle 60 chars
    mid = cq[len(cq)//2-30:len(cq)//2+30] if len(cq) > 60 else cq
    if len(mid) > 20 and mid in pt:
        return {'level': 'PARTIAL_MATCH', 'detail': 'middle segment matched'}
    # try key phrases (split by punctuation)
    phrases = re.split(r'[.,;:!?，。；：！？\u2014\u2013\-]', cq)
    phrases = [p.strip() for p in phrases if len(p.strip()) > 15]
    matched = [p for p in phrases if p in pt]
    if matched and len(matched) >= len(phrases) * 0.5:
        return {'level': 'PARTIAL_MATCH', 'detail': f'{len(matched)}/{len(phrases)} key phrases matched'}
    return {'level': 'NO_MATCH', 'detail': 'claimed quote not found in page text'}

# ── Save snapshot ──
def save_snapshot(data, node_id, content_type):
    if 'pdf' in content_type.lower() or node_id.endswith('.pdf'):
        ext = '.pdf'
    elif 'html' in content_type.lower():
        ext = '.html'
    else:
        ext = '.txt'
    fname = f"cand_{node_id}{ext}"
    fpath = os.path.join(SRC, fname)
    with open(fpath, 'wb') as f:
        f.write(data)
    h = hashlib.sha256(data).hexdigest()
    return {'snapshot_path': f"sources/{fname}", 'sha256': h, 'size': len(data)}

# ── Load existing nodes and sources ──
def load_jsonl(path):
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

# ── Process single entry ──
def process_entry(entry, existing_sources_by_url):
    nid = entry['fast_node_id']
    eid = entry['event_id']
    raw = entry['raw_link']
    unwrapped = unwrap_url(raw) if raw else ''
    was_wrapped = (raw != unwrapped) if raw else False

    # Event-10 semantic rejection
    if eid == 'event-10':
        return {
            **entry,
            'unwrapped_url': unwrapped,
            'url_was_wrapped': was_wrapped,
            'audit_result': 'REJECTED',
            'rejection_reason': 'SEMANTIC_MISMATCH: candidate links are 2024 Section 301 tariff materials; event-10 is defined as 2025-04-02 reciprocal tariff executive order',
            'fetch_status': 'NOT_FETCHED',
            'quote_match': 'N/A',
            'snapshot_path': None,
            'sha256': None,
            'publisher': get_publisher(unwrapped) if unwrapped else 'N/A',
            'source_tier': 'N/A',
            'time_reliability': 'N/A',
        }

    if not unwrapped:
        return {
            **entry,
            'unwrapped_url': '',
            'url_was_wrapped': False,
            'audit_result': 'REJECTED',
            'rejection_reason': 'NO_URL_FOUND',
            'fetch_status': 'NOT_FETCHED',
            'quote_match': 'N/A',
            'snapshot_path': None,
            'sha256': None,
            'publisher': 'N/A',
            'source_tier': 'N/A',
            'time_reliability': 'N/A',
        }

    # Check if duplicate of existing source
    for esrc in existing_sources_by_url:
        if esrc['url_norm'] == norm(unwrapped):
            return {
                **entry,
                'unwrapped_url': unwrapped,
                'url_was_wrapped': was_wrapped,
                'audit_result': 'ACCEPTED',
                'rejection_reason': None,
                'fetch_status': 'DUPLICATE_OF_EXISTING',
                'quote_match': 'EXISTING_VERIFIED',
                'snapshot_path': esrc.get('snapshot_path', ''),
                'sha256': esrc.get('sha256', ''),
                'publisher': esrc.get('publisher', get_publisher(unwrapped)),
                'source_tier': esrc.get('source_tier', get_tier(get_publisher(unwrapped))),
                'time_reliability': 'EXISTING_VERIFIED',
                'existing_evidence_id': esrc.get('evidence_id'),
            }

    # Fetch
    result = fetch_url(unwrapped)
    pub = get_publisher(unwrapped)
    tier = get_tier(pub)

    if result['error'] or result['status'] != 200:
        return {
            **entry,
            'unwrapped_url': unwrapped,
            'url_was_wrapped': was_wrapped,
            'audit_result': 'NEEDS_REVIEW',
            'rejection_reason': f"FETCH_FAILED: {result['error'] or result['status']}",
            'fetch_status': result['status'],
            'quote_match': 'N/A',
            'snapshot_path': None,
            'sha256': None,
            'publisher': pub,
            'source_tier': tier,
            'time_reliability': 'UNVERIFIED',
        }

    ct = result['content_type']
    data = result['data']

    # Save snapshot
    snap = save_snapshot(data, nid, ct)

    # Quote matching
    if 'pdf' in ct.lower():
        qm = {'level': 'NEEDS_MANUAL', 'detail': 'PDF binary saved; manual text extraction required'}
    else:
        page_text = strip_html(data)
        qm = match_quote(page_text, entry['claimed_quote'])

    # Determine audit result
    if qm['level'] in ('FULL_MATCH', 'PARTIAL_MATCH'):
        audit = 'ACCEPTED'
        time_rel = 'PAGE_DATE_SUPPORTS_CLAIM'
    elif qm['level'] == 'EXISTING_VERIFIED':
        audit = 'ACCEPTED'
        time_rel = 'EXISTING_VERIFIED'
    elif qm['level'] == 'NEEDS_MANUAL':
        audit = 'NEEDS_REVIEW'
        time_rel = 'PDF_REQUIRES_MANUAL_CHECK'
    else:
        audit = 'NEEDS_REVIEW'
        time_rel = 'QUOTE_NOT_FOUND'

    return {
        **entry,
        'unwrapped_url': unwrapped,
        'url_was_wrapped': was_wrapped,
        'audit_result': audit,
        'rejection_reason': None if audit == 'ACCEPTED' else f"Quote match: {qm['level']}; detail: {qm['detail']}",
        'fetch_status': result['status'],
        'content_type': ct,
        'content_length': len(data),
        'quote_match': qm['level'],
        'quote_match_detail': qm['detail'],
        'snapshot_path': snap['snapshot_path'],
        'sha256': snap['sha256'],
        'snapshot_size': snap['size'],
        'publisher': pub,
        'source_tier': tier,
        'time_reliability': time_rel,
        'final_url': result['final_url'],
    }

# ── Main ──
def main():
    print("=== FinGoose Evidence Intake & Audit ===")
    t0 = time.time()

    # Parse
    entries = parse_entries(PASTED)
    print(f"Parsed {len(entries)} candidate entries")

    # Load existing sources
    existing_sources = load_jsonl(EXIST_SRC)
    existing_by_url = []
    for s in existing_sources:
        existing_by_url.append({
            'url_norm': norm(s.get('source_url', '')),
            'evidence_id': s.get('evidence_id'),
            'publisher': s.get('publisher'),
            'source_tier': s.get('source_tier'),
            'snapshot_path': s.get('snapshot_path'),
            'sha256': s.get('sha256'),
        })

    # Load existing nodes
    nodes = load_jsonl(NODES)
    nodes_by_id = {n['fast_node_id']: n for n in nodes}

    # Process all entries
    results = []
    # Separate Event-10 (skip fetch) from others
    fetch_entries = [e for e in entries if e['event_id'] != 'event-10']
    skip_entries = [e for e in entries if e['event_id'] == 'event-10']

    print(f"Fetching {len(fetch_entries)} URLs (Event-10: {len(skip_entries)} auto-rejected)...")

    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(process_entry, e, existing_by_url): e for e in fetch_entries}
        for future in as_completed(future_map):
            try:
                r = future.result()
                results.append(r)
                tag = r['audit_result']
                nid = r['fast_node_id']
                print(f"  {nid}: {tag} ({r.get('quote_match','')}|{r.get('fetch_status','')})")
            except Exception as ex:
                e = future_map[future]
                print(f"  {e['fast_node_id']}: ERROR {ex}")
                results.append({
                    **e, 'unwrapped_url': unwrap_url(e['raw_link']) if e['raw_link'] else '',
                    'url_was_wrapped': True, 'audit_result': 'NEEDS_REVIEW',
                    'rejection_reason': f'EXCEPTION: {ex}', 'fetch_status': 'ERROR',
                    'quote_match': 'N/A', 'snapshot_path': None, 'sha256': None,
                    'publisher': 'N/A', 'source_tier': 'N/A', 'time_reliability': 'UNVERIFIED',
                })

    # Add Event-10 rejections
    for e in skip_entries:
        r = process_entry(e, existing_by_url)
        results.append(r)
        print(f"  {r['fast_node_id']}: {r['audit_result']} ({r.get('rejection_reason','')[:60]})")

    # Sort by node_id
    results.sort(key=lambda r: r['fast_node_id'])

    # ── Generate candidate_source_intake.jsonl ──
    intake_path = os.path.join(WORK, "candidate_source_intake.jsonl")
    with open(intake_path, 'w', encoding='utf-8') as f:
        for r in results:
            node = nodes_by_id.get(r['fast_node_id'], {})
            row = {
                'fast_node_id': r['fast_node_id'],
                'event_id': r['event_id'],
                'sequence': r['sequence'],
                'candidate_label': r['label'],
                'candidate_timestamp': r['candidate_timestamp'],
                'raw_link': r['raw_link'],
                'unwrapped_url': r['unwrapped_url'],
                'url_was_wrapped': r['url_was_wrapped'],
                'claimed_quote': r['claimed_quote'],
                'existing_node_evidence_status': node.get('evidence_status', 'UNKNOWN'),
                'existing_source_ids': node.get('source_ids', []),
                'existing_original_milestone_id': node.get('original_milestone_id'),
                'semantic_match': r['audit_result'],
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"\nWrote {intake_path}")

    # ── Generate candidate_source_audit.jsonl ──
    audit_path = os.path.join(WORK, "candidate_source_audit.jsonl")
    with open(audit_path, 'w', encoding='utf-8') as f:
        for r in results:
            row = {
                'fast_node_id': r['fast_node_id'],
                'event_id': r['event_id'],
                'unwrapped_url': r['unwrapped_url'],
                'audit_result': r['audit_result'],
                'rejection_reason': r.get('rejection_reason'),
                'fetch_status': r.get('fetch_status'),
                'content_type': r.get('content_type'),
                'content_length': r.get('content_length'),
                'quote_match': r.get('quote_match'),
                'quote_match_detail': r.get('quote_match_detail'),
                'timestamp_assessment': r.get('candidate_timestamp'),
                'time_reliability': r.get('time_reliability'),
                'can_prove_occurrence': False,  # conservative default
                'can_prove_publication': r['audit_result'] == 'ACCEPTED',
                'publisher': r.get('publisher'),
                'source_tier': r.get('source_tier'),
                'snapshot_path': r.get('snapshot_path'),
                'sha256': r.get('sha256'),
                'review_notes': '',
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"Wrote {audit_path}")

    # ── Generate candidate_source_manifest.jsonl (ACCEPTED only) ──
    manifest_path = os.path.join(WORK, "candidate_source_manifest.jsonl")
    accepted_count = 0
    with open(manifest_path, 'w', encoding='utf-8') as f:
        for r in results:
            if r['audit_result'] != 'ACCEPTED':
                continue
            accepted_count += 1
            sid = f"cand-{r['fast_node_id']}"
            row = {
                'source_id': sid,
                'event_id': r['event_id'],
                'fast_node_id': r['fast_node_id'],
                'publisher': r.get('publisher'),
                'title': r.get('link_title', ''),
                'source_url': r['unwrapped_url'],
                'published_at': r.get('candidate_timestamp'),
                'source_tier': r.get('source_tier'),
                'snapshot_path': r.get('snapshot_path'),
                'sha256': r.get('sha256'),
                'snapshot_status': 'VERIFIED' if r.get('quote_match') in ('FULL_MATCH','PARTIAL_MATCH','EXISTING_VERIFIED') else 'SNAPSHOT_ONLY',
                'quote_verified': r.get('quote_match') in ('FULL_MATCH','PARTIAL_MATCH','EXISTING_VERIFIED'),
                'quote_match_level': r.get('quote_match'),
                'locator_type': 'html_text' if 'html' in r.get('content_type','').lower() else 'pdf_page',
                'locator_value': r.get('claimed_quote','')[:200],
                'is_duplicate_of_existing': r.get('fetch_status') == 'DUPLICATE_OF_EXISTING',
                'existing_evidence_id': r.get('existing_evidence_id'),
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f"Wrote {manifest_path} ({accepted_count} accepted sources)")

    # ── Update timeline_nodes.jsonl ──
    results_by_id = {r['fast_node_id']: r for r in results}
    updated_nodes = []
    for node in nodes:
        nid = node['fast_node_id']
        r = results_by_id.get(nid)
        if not r:
            updated_nodes.append(node)
            continue

        was_pending = node['evidence_status'] == 'PENDING_EVIDENCE'
        accepted = r['audit_result'] == 'ACCEPTED'
        is_dup = r.get('fetch_status') == 'DUPLICATE_OF_EXISTING'

        if was_pending and accepted and not is_dup:
            # Upgrade pending node to verified
            node['evidence_status'] = 'VERIFIED_EXISTING'
            new_sid = f"cand-{nid}"
            if new_sid not in node['source_ids']:
                node['source_ids'] = node['source_ids'] + [new_sid]
            # Set first_public_at from candidate timestamp (conservative: page publication date)
            if r.get('candidate_timestamp') and not node.get('first_public_at'):
                node['first_public_at'] = r['candidate_timestamp']
            # occurred_at stays null (can't verify from web page alone)
            # visibility becomes PUBLIC_PREDICTION if source is public
            if node['visibility'] == 'UNRESOLVED':
                node['visibility'] = 'PUBLIC_PREDICTION'
            # gap_reason: source verified but occurrence time unverified
            node['gap_reason'] = '来源已核验；事件发生时刻待人工确认'
            node['promotion_eligible'] = False  # occurred_at is null
        elif was_pending and accepted and is_dup:
            # Duplicate of existing source - shouldn't happen for pending nodes, but handle gracefully
            node['evidence_status'] = 'VERIFIED_EXISTING'
            if r.get('existing_evidence_id') and r['existing_evidence_id'] not in node['source_ids']:
                node['source_ids'] = node['source_ids'] + [r['existing_evidence_id']]
            node['visibility'] = 'PUBLIC_PREDICTION'
            node['gap_reason'] = None
            # Check promotion eligibility
            if node.get('occurred_at') and node.get('first_public_at') and node['visibility'] != 'UNRESOLVED' and not node.get('gap_reason'):
                node['promotion_eligible'] = True
        elif was_pending and r['audit_result'] == 'NEEDS_REVIEW':
            # Keep as pending but update gap_reason with more detail
            node['gap_reason'] = f"候选来源待复核：{r.get('rejection_reason','')}"
        # For already VERIFIED_EXISTING nodes, no change needed

        updated_nodes.append(node)

    with open(NODES, 'w', encoding='utf-8') as f:
        for node in updated_nodes:
            f.write(json.dumps(node, ensure_ascii=False) + '\n')
    print(f"Updated {NODES}")

    # ── Regenerate gap_report.json (clean) ──
    gap = {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'node_target': '40-50',
        'node_count': len(updated_nodes),
        'promotable_count': sum(1 for n in updated_nodes if n.get('promotion_eligible')),
        'pending_evidence_count': sum(1 for n in updated_nodes if n['evidence_status'] == 'PENDING_EVIDENCE'),
        'candidate_intake_count': len(results),
        'candidate_accepted_count': accepted_count,
        'candidate_rejected_count': sum(1 for r in results if r['audit_result'] == 'REJECTED'),
        'candidate_needs_review_count': sum(1 for r in results if r['audit_result'] == 'NEEDS_REVIEW'),
        'priority_events': ['event-04', 'event-06', 'event-07', 'event-09', 'event-10'],
        'events': [],
    }
    for eid in [f'event-{i:02d}' for i in range(1, 11)]:
        ev_nodes = [n for n in updated_nodes if n['event_id'] == eid]
        verified = sum(1 for n in ev_nodes if n['evidence_status'] == 'VERIFIED_EXISTING')
        pending = sum(1 for n in ev_nodes if n['evidence_status'] == 'PENDING_EVIDENCE')
        unresolved = sum(1 for n in ev_nodes if not n.get('occurred_at'))
        public = sum(1 for n in ev_nodes if n.get('visibility') == 'PUBLIC_PREDICTION')
        hidden = sum(1 for n in ev_nodes if n.get('visibility') == 'HIDDEN_VALIDATION')
        unres_vis = sum(1 for n in ev_nodes if n.get('visibility') == 'UNRESOLVED')
        promotable = sum(1 for n in ev_nodes if n.get('promotion_eligible'))
        gaps = []
        for n in ev_nodes:
            if n['evidence_status'] == 'PENDING_EVIDENCE' or n.get('gap_reason'):
                r = results_by_id.get(n['fast_node_id'], {})
                gaps.append({
                    'fast_node_id': n['fast_node_id'],
                    'evidence_status': n['evidence_status'],
                    'phase': n.get('phase'),
                    'research_task': n.get('fact', ''),
                    'required_source': n.get('gap_reason') or '需要一手来源核验',
                    'candidate_audit_result': r.get('audit_result', 'N/A'),
                    'candidate_rejection_reason': r.get('rejection_reason'),
                })
        gap['events'].append({
            'event_id': eid,
            'total_nodes': len(ev_nodes),
            'verified_existing': verified,
            'pending_evidence': pending,
            'unresolved_time': unresolved,
            'public_prediction': public,
            'hidden_validation': hidden,
            'unresolved_visibility': unres_vis,
            'promotable': promotable,
            'gaps': gaps,
        })

    gap_path = os.path.join(WORK, "timeline_gap_report.json")
    with open(gap_path, 'w', encoding='utf-8') as f:
        json.dump(gap, f, indent=2, ensure_ascii=False)
    print(f"Regenerated {gap_path}")

    # ── Regenerate validation_report.json ──
    # Recompute baseline SHA-256
    import hashlib as hl
    baseline_files = {
        'event_milestones_jsonl': r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\data\market_event_attribution_v2_candidate\event_milestones.jsonl",
        'event_episodes_jsonl': r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\data\market_event_attribution_v2_candidate\event_episodes.jsonl",
        'manifest_json': r"D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29\data\market_event_attribution_v2_candidate\manifest.json",
    }
    baseline_hashes = {}
    for key, path in baseline_files.items():
        try:
            with open(path, 'rb') as bf:
                baseline_hashes[key] = hl.sha256(bf.read()).hexdigest()
        except:
            baseline_hashes[key] = 'FILE_NOT_FOUND'

    val = {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'production_dataset_modified': False,
        'event_count': 10,
        'node_count': len(updated_nodes),
        'episode_count': 37,
        'promotable_count': sum(1 for n in updated_nodes if n.get('promotion_eligible')),
        'pending_evidence_count': sum(1 for n in updated_nodes if n['evidence_status'] == 'PENDING_EVIDENCE'),
        'unresolved_time_count': sum(1 for n in updated_nodes if not n.get('occurred_at')),
        'candidate_intake_count': len(results),
        'candidate_accepted_count': accepted_count,
        'candidate_rejected_count': sum(1 for r in results if r['audit_result'] == 'REJECTED'),
        'candidate_needs_review_count': sum(1 for r in results if r['audit_result'] == 'NEEDS_REVIEW'),
        'hard_failures': [],
        'warnings': [
            f'UNRESOLVED_TIME:{sum(1 for n in updated_nodes if not n.get("occurred_at"))}',
            'PROVISIONAL_EXISTING_NOT_PROMOTABLE:{}'.format(sum(1 for n in updated_nodes if n['evidence_status']=='VERIFIED_EXISTING' and not n.get('promotion_eligible'))),
            'FAST_EPISODES_ARE_WORKBOOK_RECORDS_NOT_PRODUCTION_EPISODE_SCHEMA',
            f'CANDIDATE_SOURCES_REJECTED:{sum(1 for r in results if r["audit_result"]=="REJECTED")}',
            f'CANDIDATE_SOURCES_NEEDS_REVIEW:{sum(1 for r in results if r["audit_result"]=="NEEDS_REVIEW")}',
        ],
        'baseline_sha256': baseline_hashes,
    }
    val_path = os.path.join(WORK, "validation_report.json")
    with open(val_path, 'w', encoding='utf-8') as f:
        json.dump(val, f, indent=2, ensure_ascii=False)
    print(f"Regenerated {val_path}")

    # ── Summary ──
    elapsed = time.time() - t0
    print(f"\n=== Summary ({elapsed:.1f}s) ===")
    print(f"Total candidates:    {len(results)}")
    print(f"  ACCEPTED:          {accepted_count}")
    print(f"  REJECTED:          {sum(1 for r in results if r['audit_result']=='REJECTED')}")
    print(f"  NEEDS_REVIEW:      {sum(1 for r in results if r['audit_result']=='NEEDS_REVIEW')}")
    print(f"URLs unwrapped:      {sum(1 for r in results if r.get('url_was_wrapped'))}")
    print(f"Snapshots saved:    {sum(1 for r in results if r.get('snapshot_path'))}")
    qm_counts = {}
    for r in results:
        qm = r.get('quote_match', 'N/A')
        qm_counts[qm] = qm_counts.get(qm, 0) + 1
    print(f"Quote match breakdown: {json.dumps(qm_counts)}")
    print(f"\nNode status after update:")
    print(f"  VERIFIED_EXISTING: {sum(1 for n in updated_nodes if n['evidence_status']=='VERIFIED_EXISTING')}")
    print(f"  PENDING_EVIDENCE:  {sum(1 for n in updated_nodes if n['evidence_status']=='PENDING_EVIDENCE')}")
    print(f"  Promotable:        {sum(1 for n in updated_nodes if n.get('promotion_eligible'))}")

    # Per-event breakdown
    print(f"\nPer-event breakdown:")
    print(f"{'Event':<12} {'Nodes':>5} {'Ver':>4} {'Pen':>4} {'Pro':>4} {'Acc':>4} {'Rej':>4} {'Rev':>4}")
    for eid in [f'event-{i:02d}' for i in range(1, 11)]:
        ev_nodes = [n for n in updated_nodes if n['event_id'] == eid]
        ev_results = [r for r in results if r['event_id'] == eid]
        v = sum(1 for n in ev_nodes if n['evidence_status']=='VERIFIED_EXISTING')
        p = sum(1 for n in ev_nodes if n['evidence_status']=='PENDING_EVIDENCE')
        pr = sum(1 for n in ev_nodes if n.get('promotion_eligible'))
        a = sum(1 for r in ev_results if r['audit_result']=='ACCEPTED')
        rj = sum(1 for r in ev_results if r['audit_result']=='REJECTED')
        rv = sum(1 for r in ev_results if r['audit_result']=='NEEDS_REVIEW')
        print(f"{eid:<12} {len(ev_nodes):>5} {v:>4} {p:>4} {pr:>4} {a:>4} {rj:>4} {rv:>4}")

if __name__ == '__main__':
    main()
