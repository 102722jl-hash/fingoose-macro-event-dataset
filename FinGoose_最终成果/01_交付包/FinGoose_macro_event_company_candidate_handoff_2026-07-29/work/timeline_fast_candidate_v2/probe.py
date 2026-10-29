# -*- coding: utf-8 -*-
import urllib.request, ssl, json, re, io, sys

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/pdf,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def clean(html):
    html = re.sub(r'(?is)<script.*?</script>', ' ', html)
    html = re.sub(r'(?is)<style.*?</style>', ' ', html)
    html = re.sub(r'(?is)<[^>]+>', ' ', html)
    html = re.sub(r'&nbsp;', ' ', html)
    html = re.sub(r'&amp;', '&', html)
    html = re.sub(r'&quot;', '"', html)
    html = re.sub(r'&#39;|&apos;', "'", html)
    html = re.sub(r'&gt;', '>', html)
    html = re.sub(r'&lt;', '<', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()

def try_url(url, match, timeout=30):
    try:
        req = urllib.request.Request(url, headers=HEADERS, method='GET')
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            code = r.getcode()
            data = r.read()
            ctype = r.headers.get('Content-Type','')
        is_pdf = 'pdf' in ctype or url.lower().endswith('.pdf') or data[:4]==b'%PDF'
        if is_pdf:
            from pypdf import PdfReader
            txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
            kind='PDF'
        else:
            try:
                html = data.decode('utf-8', 'ignore')
            except Exception:
                html = data.decode('latin-1', 'ignore')
            txt = clean(html)
            kind='HTML'
        found = match.lower() in txt.lower()
        snippet = ''
        if found:
            idx = txt.lower().find(match.lower())
            snippet = txt[max(0,idx-120):idx+len(match)+120]
        return dict(url=url, code=code, len=len(data), ctype=ctype, kind=kind, found=found, match=match, snippet=snippet[:400])
    except Exception as e:
        return dict(url=url, error=str(e)[:200], match=match)

# node -> list of candidate urls + match
CAND = {
 'event-02-M01': [
    ('https://en.kremlin.ru/events/president/news/67843', 'donetsk people'),
    ('https://en.kremlin.ru/events/president/news/67843', 'immediately recognize the sovereignty'),
 ],
 'event-06-M04': [
    ('https://www.spa.gov.sa/en/N1961204', '1 million'),
    ('https://www.spa.gov.sa/en/N1961204', 'one million'),
    ('https://spa.gov.sa/en/N1961204', 'million barrels'),
 ],
 'event-07-M03': [
    ('https://www.imo.org/en/MediaCentre/PressBriefings/pages/Red-Sea-statement.aspx', 'galaxy leader'),
    ('https://www.imo.org/en/MediaCentre/PressBriefings/pages/Galaxy-Leader-seizure.aspx', 'galaxy leader'),
 ],
 'event-08-M01': [
    ('https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2023/mp230728a.htm', '1.0 percent'),
    ('https://www.news.cn/english/20230728/c1129773834.htm', '1.0 percent'),
    ('https://www.xinhuanet.com/english/20230728/c1129773834.htm', '1.0 percent'),
 ],
 'event-08-M03': [
    ('https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2024/mp240319a.htm', '0 to 0.1 percent'),
    ('https://www.xinhuanet.com/english/20240319/394d44c6e53f45ee88b366f9e1fb97ab/c.html', '0 to 0.1 percent'),
    ('https://english.news.cn/20240319/394d44c6e53f45ee88b366f9e1fb97ab/c.html', '0 to 0.1 percent'),
 ],
}

for node, cands in CAND.items():
    print('='*70)
    print('NODE', node)
    for url, match in cands:
        r = try_url(url, match)
        print(json.dumps(r, ensure_ascii=False)[:600])
