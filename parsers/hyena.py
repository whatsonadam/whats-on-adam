"""FC Hyena parser. Input: raw HTML of the ticketing list
https://tickets.fchyena.nl/fchyena/nl/flow_configs/1/z_events_list  (one request, every future show, Dutch dates
with year, e.g. "wo 14 oktober 2026, 10:50"). fchyena.nl itself is a Framer site without a readable feed.
Titles are the ticketing titles: "Beloved, The" is turned into "The Beloved" and "(2D OV)" style tags are dropped."""
import datetime, re
from bs4 import BeautifulSoup

BASE = "https://tickets.fchyena.nl"
NL = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
      "september": 9, "oktober": 10, "november": 11, "december": 12}
DATE = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(\d{4}),?\s+(\d{1,2}):(\d\d)", re.I)

def _title(t):
    t = re.sub(r"\s*\(\s*[23]D(?:\s+[A-Za-z]+)?\s*\)", "", t).strip()
    m = re.fullmatch(r"(.+), (The|A|An|De|Het|Een|Le|La|Les|L')", t)
    if m: t = m.group(2) + (" " if not m.group(2).endswith("'") else "") + m.group(1)
    return t

def parse(text, today):
    if "<" not in text: return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for tr in BeautifulSoup(text, "html.parser").select("tr"):
        h4, p, a = tr.find("h4"), tr.find("p"), tr.find("a", href=True)
        if not h4 or not p: continue
        title = _title(h4.get_text(" ", strip=True))
        m = DATE.search(p.get_text(" ", strip=True))
        if not title or not m: continue
        mon = NL.get(m.group(2).lower())
        if not mon: continue
        try: d = datetime.date(int(m.group(3)), mon, int(m.group(1)))
        except ValueError: continue
        if d < today or d > end: continue
        h = f"{int(m.group(4)):02d}:{m.group(5)}"
        k = (title, d, h)
        if k in seen: continue
        seen.add(k)
        u = (BASE + a["href"]) if a and a["href"].startswith("/") else (a["href"] if a else BASE + "/fchyena/nl/flow_configs/1/z_events_list")
        out.append({"t": title, "d": d.isoformat(), "h": h, "v": "FC Hyena", "u": u, "c": "film", "s": "hyena"})
    out.sort(key=lambda e: (e["d"], e["h"]))
    return out
