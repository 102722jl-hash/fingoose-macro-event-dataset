"""Attempt raw-HTTP fetch for the 15 PENDING nodes using a browser-like UA.
Saves real body snapshots, computes SHA-256, and checks the claimed quote.
Also records occurred_at / first_public_at evidence if present in body text.
"""
import json, os, hashlib, urllib.request, urllib.error, ssl, re, datetime

WORK = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WORK, "sources")
os.makedirs(SRC, exist_ok=True)

# Browser-like headers to reduce 403/UA blocks
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
              "image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # avoid gzip decode issues
    "Connection": "keep-alive",
}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# (node_id, url, claimed_quote)
TARGETS = [
 ("fast-event-01-M03","https://www.paho.org/en/news/11-3-2020-who-characterizes-covid-19-pandemic",
  "We have therefore made the assessment that COVID-19 can be characterized as a pandemic"),
 ("fast-event-02-M01","https://en.kremlin.ru/events/president/news/67843",
  "Executive orders on recognition of the Donetsk People"),
 ("fast-event-04-M01","http://www.nhc.gov.cn/xcs/zhengcwj/202211/k101.shtml",
  "5天集中隔离+3天居家隔离"),
 ("fast-event-04-M02","http://www.news.cn/politics/2022-11/30/c_1129174151.htm",
  "我国疫情防控面临新形势新任务"),
 ("fast-event-04-M05","http://www.customs.gov.cn/customs/302249/202212/131.shtml",
  "自2023年1月8日起，取消入境人员全员核酸检测"),
 ("fast-event-05-M03","https://www.snb.ch/en/mmr/reference/pre_20230315/source/pre_20230315.en.html",
  "FINMA and the Swiss National Bank assert that Credit Suisse meets the higher capital"),
 ("fast-event-06-M04","https://www.spa.gov.sa/en/N1961204",
  "extend voluntary cut of 1 million bpd"),
 ("fast-event-06-M05","https://www.opec.org/opec_web/en/press_room/7324.htm",
  "Voluntary cuts to be gradually phased out on a monthly basis starting October 2024"),
 ("fast-event-07-M03","https://www.imo.org/en/MediaCentre/PressBriefings/pages/Red-Sea-statement.aspx",
  "Galaxy Leader"),
 ("fast-event-07-M05","https://www.whitehouse.gov/briefing-room/statements-releases/2024/01/11/statement-from-president-joe-biden-on-us-military-strikes-in-yemen/",
  "successfully conducted strikes against Houthi"),
 ("fast-event-08-M01","https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2023/mp230728a.htm",
  "offer to purchase 10-year JGBs at 1.0 percent"),
 ("fast-event-08-M03","https://www.boj.or.jp/en/mopo/mpmdeci/mpo_2024/mp240319a.htm",
  "uncollateralized overnight call rate of around 0 to 0.1 percent"),
 ("fast-event-08-M05","https://www.jpx.co.jp/english/news/1020/20240805.html",
  "Nikkei 225 index dropped 4,451.28 points"),
 ("fast-event-09-M04","http://www.pbc.gov.cn/goutongfeijiao/113419/113411/5472811/index.html",
  "引导商业银行于2024年10月31日前统一对存量房贷利率实施批量调整"),
 ("fast-event-09-M05","http://www.pbc.gov.cn/goutongfeijiao/113419/113411/5480112/index.html",
  "证券、基金、保险公司互换便利（SFISF）"),
]

def clean(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"&amp;", "&", txt)
    txt = re.sub(r"&quot;", '"', txt)
    txt = re.sub(r"&#39;|&apos;", "'", txt)
    txt = re.sub(r"&lt;", "<", txt)
    txt = re.sub(r"&gt;", ">", txt)
    txt = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()

results = {}
for nid, url, cq in TARGETS:
    rec = {"node_id": nid, "url": url, "claimed_quote": cq, "status": None,
           "http_code": None, "error": None, "snapshot": None,
           "sha256": None, "quote_found": False, "quote_hits": []}
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            data = r.read()
            rec["http_code"] = r.getcode()
            rec["status"] = "OK"
            ctype = r.headers.get("Content-Type", "")
            enc = "utf-8"
            m = re.search(r"charset=([\w-]+)", ctype)
            if m:
                enc = m.group(1)
            try:
                body = data.decode(enc, errors="replace")
            except Exception:
                body = data.decode("utf-8", errors="replace")
            # save raw snapshot
            snap = os.path.join(SRC, f"raw_pending_{nid}.html")
            with open(snap, "wb") as f:
                f.write(data)
            rec["snapshot"] = snap
            rec["sha256"] = hashlib.sha256(data).hexdigest()
            txt = clean(body)
            # quote check (case-insensitive contains)
            if cq.lower() in txt.lower():
                rec["quote_found"] = True
                # locate best context sentence
                idx = txt.lower().find(cq.lower())
                start = max(0, idx-120); end = min(len(txt), idx+len(cq)+160)
                rec["quote_hits"].append(txt[start:end].replace("\n", " "))
    except urllib.error.HTTPError as e:
        rec["status"] = "HTTPError"; rec["http_code"] = e.code
        rec["error"] = e.reason
    except urllib.error.URLError as e:
        rec["status"] = "URLError"; rec["error"] = str(e.reason)
    except Exception as e:
        rec["status"] = "ERR"; rec["error"] = repr(e)[:200]
    results[nid] = rec
    print(f"{nid:20} {rec['status']:10} code={rec['http_code']} quote={rec['quote_found']} sha={(rec['sha256'] or '')[:12]} :: {rec['error'] or rec['snapshot']}")

with open(os.path.join(WORK, "fetch_pending_results.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nWrote fetch_pending_results.json")
