"""Wayback Machine fallback: for each of the 15 PENDING nodes, query the
Wayback availability API, fetch the closest archived snapshot via raw HTTP,
save a real-body snapshot, compute SHA-256, and verify the claimed quote.
This covers both dead-URL and bot-walled nodes in one pass.
"""
import json, os, hashlib, urllib.request, urllib.error, ssl, re, time

WORK = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WORK, "sources")
os.makedirs(SRC, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

TARGETS = [
 ("fast-event-01-M03","https://www.paho.org/en/news/11-3-2020-who-characterizes-covid-19-pandemic",
  "characterized as a pandemic"),
 ("fast-event-02-M01","https://en.kremlin.ru/events/president/news/67843",
  "recognition of the Donetsk"),
 ("fast-event-05-M03","https://www.snb.ch/en/mmr/reference/pre_20230315/source/pre_20230315.en.html",
  "Credit Suisse meets the higher capital"),
 ("fast-event-06-M04","https://www.spa.gov.sa/en/N1961204",
  "1 million bpd"),
 ("fast-event-07-M03","https://www.imo.org/en/MediaCentre/PressBriefings/pages/Red-Sea-statement.aspx",
  "Galaxy Leader"),
 ("fast-event-07-M05","https://www.whitehouse.gov/briefing-room/statements-releases/2024/01/11/statement-from-president-joe-biden-on-us-military-strikes-in-yemen/",
  "strikes against Houthi"),
 ("fast-event-08-M01","https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2023/mp230728a.htm",
  "1.0 percent"),
 ("fast-event-08-M03","https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2024/mp240319a.htm",
  "0 to 0.1 percent"),
]

def clean(html):
    html=re.sub(r"(?is)<script.*?</script>"," ",html)
    html=re.sub(r"(?is)<style.*?</style>"," ",html)
    txt=re.sub(r"(?s)<[^>]+>"," ",html)
    txt=re.sub(r"&nbsp;"," ",txt)
    txt=re.sub(r"&#(\d+);",lambda m:chr(int(m.group(1))),txt)
    txt=re.sub(r"[ \t]+"," ",txt); txt=re.sub(r"\s+"," ",txt)
    return txt.strip()

def http_get(url, binary=False):
    req=urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        data=r.read()
        return r.getcode(), data

def wayback_closest(url):
    api=f"https://archive.org/wayback/available?url={urllib.parse.quote(url, safe='')}"
    for attempt in range(4):
        try:
            code,data=http_get(api)
            j=json.loads(data.decode("utf-8", errors="replace"))
            snap=j.get("archived_snapshots",{}).get("closest",{})
            if snap.get("available"):
                return snap.get("url"), snap.get("timestamp")
            return None, None
        except urllib.error.HTTPError as e:
            if e.code==429:
                time.sleep(8*(attempt+1)); continue
            return None, f"api_err:{e}"
        except Exception as e:
            return None, f"api_err:{e}"
    return None, "api_429_retries_exhausted"

results={}
for nid,url,cq in TARGETS:
    rec={"node_id":nid,"orig_url":url,"claimed_quote":cq}
    wb, ts = wayback_closest(url)
    rec["wayback_url"]=wb; rec["wayback_ts"]=ts
    time.sleep(3)  # avoid archive.org rate limiting
    if not wb:
        rec.update(status="NO_WAYBACK", snapshot=None, sha256=None, quote_found=False)
        print(f"{nid:20} NO_WAYBACK ({ts})")
        continue
    # try snapshot, with if_ (no-JS) variant fallback
    try:
        code,data=http_get(wb)
        body=data.decode("utf-8", errors="replace")
        # if it looks like a redirect/JS shell, try the 'if_' modifier
        if "window.location" in body[:500] or len(clean(body))<200:
            wb2=wb.replace("/web/","/web/",1)
            # insert if_ after timestamp
            import re as _re
            m=_re.search(r"(/web/\d+)(/)", wb)
            if m:
                wb2=wb[:m.start(1)+len(m.group(1))]+"if_"+wb[m.start(1)+len(m.group(1)):]
                code,data=http_get(wb2); body=data.decode("utf-8", errors="replace")
                wb=wb2
        snap=os.path.join(SRC, f"wb_pending_{nid}.html")
        with open(snap,"wb") as f: f.write(data)
        rec["snapshot"]=snap
        rec["sha256"]=hashlib.sha256(data).hexdigest()
        txt=clean(body)
        rec["quote_found"]= cq.lower() in txt.lower()
        if rec["quote_found"]:
            i=txt.lower().find(cq.lower())
            rec["quote_hit"]=txt[max(0,i-120):i+len(cq)+160].replace("\n"," ")
        rec["status"]="OK"; rec["http_code"]=code
        print(f"{nid:20} OK ts={ts} quote={rec['quote_found']} sha={rec['sha256'][:12]} len={len(txt)}")
    except Exception as e:
        rec.update(status="FETCH_ERR", error=repr(e)[:150], snapshot=None, sha256=None, quote_found=False)
        print(f"{nid:20} FETCH_ERR {e}")
    time.sleep(0.5)

with open(os.path.join(WORK,"wayback_results.json"),"w",encoding="utf-8") as f:
    json.dump(results,f,ensure_ascii=False,indent=2)
print("\nWrote wayback_results.json")
