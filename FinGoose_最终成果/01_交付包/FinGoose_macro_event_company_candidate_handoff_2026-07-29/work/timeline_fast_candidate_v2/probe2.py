# -*- coding: utf-8 -*-
import urllib.request, ssl, re, io, json
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36','Accept':'text/html,application/xhtml+xml,*/*;q=0.8','Accept-Language':'en-US,en;q=0.9'}
def clean(html):
    html=re.sub(r'(?is)<script.*?</script>',' ',html); html=re.sub(r'(?is)<style.*?</style>',' ',html)
    html=re.sub(r'(?is)<[^>]+>',' ',html); html=re.sub(r'&nbsp;',' ',html); html=re.sub(r'&amp;','&',html)
    html=re.sub(r'&quot;','"',html); html=re.sub(r'&#39;|&apos;',"'",html); html=re.sub(r'&gt;','>',html); html=re.sub(r'&lt;','<',html)
    html=re.sub(r'\s+',' ',html); return html.strip()
def try_url(url, match, timeout=30):
    try:
        req=urllib.request.Request(url,headers=HEADERS,method='GET')
        with urllib.request.urlopen(req,timeout=timeout,context=ctx) as r:
            code=r.getcode(); data=r.read(); ctype=r.headers.get('Content-Type','')
        try: html=data.decode('utf-8','ignore')
        except: html=data.decode('latin-1','ignore')
        txt=clean(html); found=match.lower() in txt.lower(); sn=''
        if found:
            i=txt.lower().find(match.lower()); sn=txt[max(0,i-100):i+len(match)+120]
        return dict(url=url,code=code,len=len(data),found=found,snippet=sn[:360])
    except Exception as e:
        return dict(url=url,error=str(e)[:160])
CAND={
 'event-08-M01_BOJ_YCC':[
    ('https://www.boj.or.jp/en/mopo/mpmsche_minu/minu_2023/g230728.htm','1.0 percent'),
 ],
 'event-06-M04_SPA':[
    ('https://www.saudigazette.com.sa/article/635536','one million barrels per day'),
    ('https://english.aawsat.com/node/4364526','one million barrels per day'),
    ('http://www.chinaview.cn/20240304/7d2ac37b2d3a4897a544e9ee1faefe33/c.html','1 million barrels per day'),
 ],
 'event-07-M03_IMO':[
    ('https://news.un.org/en/story/2025/01/1159281','Galaxy Leader'),
    ('https://www.imo.org/en/mediacentre/pages/whatsnew-2020.aspx','Red Sea'),
 ],
}
for node,cands in CAND.items():
    print('='*70); print(node)
    for url,match in cands:
        print(json.dumps(try_url(url,match),ensure_ascii=False)[:500])
