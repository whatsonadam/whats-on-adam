"""Felix Meritis (felixmeritis.nl/programma): talks, performances, gatherings and workshops at the canal-side cultural house.

The programme list (/programma/ and /programma/page/N/) gives date (no year), categories, title and a summary. Start
time and ticket price are on each event's own page, so those are fetched once per event (one per second).
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://felixmeritis.nl/programma/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 10
MON = {"jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
DATE = re.compile(r"(\d{1,2})\s+([a-z]{3})", re.I)
CAT = [("talk", r"talk|lecture|debate|conversation|lezing|gesprek|book"), ("workshop", r"workshop|class|course"),
       ("music", r"music|concert|live|jazz|listening|sound"), ("club", r"party|club|dj"), ("theatre", r"theatre|theater|performance|dance|comedy|spoken word")]


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _items(html):
    s = BeautifulSoup(html, "html.parser")
    out = []
    for it in s.select("[data-event-list-item]"):
        a = it.select_one("a.event-list__link[href]")
        t = it.select_one(".event-list__title")
        d = it.select_one(".event-list__date")
        if not (a and t and d): continue
        out.append({"url": a["href"], "t": t.get_text(" ", strip=True), "date": d.get_text(" ", strip=True),
                    "cats": [c.get_text(" ", strip=True) for c in it.select(".event-list__category")],
                    "sub": (it.select_one(".event-list__subtitle") or t).get_text(" ", strip=True) if it.select_one(".event-list__subtitle") else "",
                    "sum": (it.select_one(".event-list__summary").get_text(" ", strip=True) if it.select_one(".event-list__summary") else "")})
    return out


def fetch(dirpath):
    """Download the list pages, then the detail page of every upcoming entry. Returns the number of events."""
    os.makedirs(dirpath, exist_ok=True)
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    urls = []
    for n in range(1, MAX_PAGES + 1):
        path = os.path.join(dirpath, f"p{n:02d}.html")
        code = _curl(BASE if n == 1 else f"{BASE}page/{n}/", path)
        if code != "200": os.remove(path) if os.path.exists(path) else None; break
        its = _items(open(path, errors="ignore").read())
        if not its: os.remove(path); break
        new = [i["url"] for i in its if i["url"] not in urls]
        if not new: os.remove(path); break      # the site repeats the first page for later page numbers
        urls += new
        time.sleep(1)
    if not urls: raise RuntimeError("no events")
    for u in dict.fromkeys(urls):
        _curl(u, os.path.join(dirpath, "detail", _slug(u) + ".html"))
        time.sleep(1)
    return len(set(urls))


def _detail(html):
    s = BeautifulSoup(html, "html.parser")
    text = s.get_text(" ", strip=True)
    m = re.search(r"Tijd\s+(\d{1,2}:\d{2})", text) or re.search(r"\bTime\s+(\d{1,2}:\d{2})", text)
    prices = [float(p.replace(",", ".")) for p in re.findall(r"€\s*(\d+(?:[.,]\d+)?)", text[:1500])]
    return (m.group(1).zfill(5) if m else None), prices


def parse_pages(pages, details, today):
    out, seen = [], set()
    for html in pages:
        for it in _items(html):
            m = DATE.search(it["date"])
            if not m or m.group(2).lower()[:3] not in MON or it["url"] in seen: continue
            seen.add(it["url"])
            mon, day = MON[m.group(2).lower()[:3]], int(m.group(1))
            try: d = datetime.date(today.year, mon, day)
            except ValueError: continue
            if d < today - datetime.timedelta(days=60): d = d.replace(year=today.year + 1)
            if d < today: continue
            h, prices = _detail(details[_slug(it["url"])]) if _slug(it["url"]) in details else (None, [])
            cats = " ".join(it["cats"]).lower()
            c = next((k for k, rx in CAT if re.search(rx, cats + " " + it["t"].lower())), "other")
            e = {"t": it["t"], "d": d.isoformat(), "v": "Felix Meritis", "u": it["url"], "c": c, "s": "felixmeritis"}
            if h: e["h"] = h
            if prices:
                lo, hi = min(prices), max(prices)
                e["p"] = clean_price(f"{lo:g}") if lo == hi else "from " + clean_price(f"{lo:g}")
                if lo == 0 and hi == 0: e["p"] = "Free"
            b = (it["sub"] + ". " if it["sub"] and it["sub"] != it["t"] else "") + it["sum"]
            if b.strip(". "): e["b"] = b[:300]
            out.append(e)
    return out
