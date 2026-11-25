"""Waag Futurelab (waag.org): open workshops, talks and meet-ups about technology and society, in English.

One page (/en/events/) lists every upcoming event with schema.org microdata: start and end time, title, a short
description and a lab label. Events labelled "make" are workshops, the rest talks.
"""
import datetime, html, re, subprocess
from bs4 import BeautifulSoup

URL = "https://waag.org/en/events/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def fetch(out):
    r = subprocess.run(["curl", "-sS", "-m", "60", "-L", "-A", UA, "-o", out, "-w", "%{http_code}", URL], capture_output=True, text=True)
    if r.stdout.strip() != "200": raise RuntimeError("http " + r.stdout.strip())
    return 1


def parse(text, today):
    out, seen = [], set()
    s = BeautifulSoup(text, "html.parser")
    for a in s.select("a.event-teaser"):
        st = a.select_one(".dt-start")
        h2 = a.select_one("h2")
        if not st or not h2: continue
        try: d = datetime.date.fromisoformat(st.get_text()[:10])
        except ValueError: continue
        if d < today: continue
        href = a.get("href") or ""
        u = href if href.startswith("http") else "https://waag.org" + href
        if u in seen: continue
        seen.add(u)
        title = re.sub(r"\s+", " ", h2.get_text(" ", strip=True))
        en = a.select_one(".dt-end")
        lab = a.select_one(".group-lab span")
        desc = a.select_one("p.description")
        cat = "workshop" if lab and "make" in (lab.get("class") or []) else "talk"
        if re.search(r"\bexpo\b|exhibition|festival|museum night|social club", title, re.I): cat = "other"   # build.py sorts these
        e = {"t": title, "d": d.isoformat(), "h": st.get_text()[11:16], "v": "Waag Futurelab", "u": u, "s": "waag", "c": cat}
        if en and en.get_text()[:10] == st.get_text()[:10]: e["eh"] = en.get_text()[11:16]
        if desc: e["b"] = re.sub(r"\s+", " ", desc.get_text(" ", strip=True))[:200]
        out.append(e)
    return out
