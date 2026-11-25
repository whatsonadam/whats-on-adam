"""Jewish Cultural Quarter (jck.nl/en/agenda): candlelight concerts and one-off programmes at the Portuguese Synagogue,
Jewish Museum and neighbours.

The agenda list gives category, date (no year) and title. Exhibitions and running items ("till March 29") are skipped.
Start time, venue and price are on each detail page, fetched once per event (one per second).
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://jck.nl"
LIST = BASE + "/en/agenda"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
DATE = re.compile(r"^([A-Za-z]+)\s+(\d{1,2})$")
TIME = re.compile(r"(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?(?:\s*[-–]\s*(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?)?", re.I)


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _clean_soup(html):
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "svg", "picture", "figure"]): t.decompose()
    return s


def _items(html):
    out = []
    for a in _clean_soup(html).select("a.agenda-item[href]"):
        t = a.select_one(".base-card__title")
        meta = a.select_one(".meta-line__content")
        after = a.select_one(".meta-line__after")
        if not (t and after): continue
        out.append({"url": BASE + a["href"] if a["href"].startswith("/") else a["href"], "t": t.get_text(" ", strip=True),
                    "cat": meta.get_text(" ", strip=True) if meta else "", "date": after.get_text(" ", strip=True)})
    return out


def fetch(dirpath):
    """Download the agenda list and the detail page of every dated entry. Returns the number of detail pages."""
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    path = os.path.join(dirpath, "list.html")
    code = _curl(LIST, path)
    if code != "200": raise RuntimeError("jck list http " + code)
    items = [i for i in _items(open(path, errors="ignore").read()) if DATE.match(i["date"])]
    if not items: raise RuntimeError("no events")
    for i in items:
        _curl(i["url"], os.path.join(dirpath, "detail", _slug(i["url"]) + ".html"))
        time.sleep(1)
    return len(items)


def _hm(h, m, ap):
    h = int(h)
    if ap:
        ap = ap.lower()
        if ap == "pm" and h < 12: h += 12
        if ap == "am" and h == 12: h = 0
    if h > 23: return None
    return f"{h:02d}:{int(m or 0):02d}"


def _detail(html):
    s = _clean_soup(html)
    text = s.get_text(" | ", strip=True)
    venue = h = eh = price = lead = None
    m = re.search(r"Location:\s*([^|]+)", text)
    if m: venue = m.group(1).strip()
    m = re.search(r"Time:\s*([^|]+)", text)
    if m:
        t = TIME.search(m.group(1))
        if t:
            ap1 = t.group(3) or t.group(6)
            h = _hm(t.group(1), t.group(2), ap1)
            if t.group(4): eh = _hm(t.group(4), t.group(5), t.group(6) or ap1)
            if h and eh and eh <= h: eh = None
    m = re.search(r"Admission:?\s*\|?\s*(.{0,200})", text)
    if m:
        seg = m.group(1)
        if re.match(r"\W*free", seg, re.I): price = "Free"
        else:
            a = re.search(r"Adult:?\s*€\s*(\d+(?:[.,]\d+)?)", seg) or re.search(r"€\s*(\d+(?:[.,]\d+)?)", seg)
            if a: price = clean_price(a.group(1))
    h1 = s.find("h1")
    if h1:
        ps = [p.get_text(" ", strip=True) for p in s.find_all("p")]
        lead = next((p for p in ps if len(p) > 60 and not p.startswith(("Location", "Time"))), None)
    return venue, h, eh, price, lead


def parse_pages(pages, details, today):
    out, seen = [], set()
    for html in pages:
        for it in _items(html):
            m = DATE.match(it["date"])
            if not m or m.group(1).lower() not in MONTHS or it["url"] in seen: continue
            seen.add(it["url"])
            mon, day = MONTHS.index(m.group(1).lower()) + 1, int(m.group(2))
            try: d = datetime.date(today.year, mon, day)
            except ValueError: continue
            if d < today: d = d.replace(year=today.year + 1)
            cat = it["cat"].lower()
            c = "music" if "concert" in cat else "other"
            if re.search(r"workshop", cat + " " + it["t"].lower()): c = "workshop"
            elif re.search(r"lecture|talk|conversation|debate", it["t"].lower()): c = "talk"
            elif re.search(r"tasting|dinner|lunch", it["t"].lower()): c = "food"
            venue, h, eh, price, lead = _detail(details[_slug(it["url"])]) if _slug(it["url"]) in details else (None, None, None, None, None)
            e = {"t": it["t"], "d": d.isoformat(), "v": venue or "Jewish Cultural Quarter", "u": it["url"], "c": c, "s": "jck"}
            if h: e["h"] = h
            if eh: e["eh"] = eh
            if price: e["p"] = price
            if lead: e["b"] = lead[:220]
            out.append(e)
    return out
