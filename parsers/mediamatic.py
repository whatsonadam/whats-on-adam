"""Mediamatic (mediamatic.net): events and workshops at Mediamatic Biotoop, Amsterdam.

The list pages (/en/events and /en/workshopcalendar) show one or two calendar blocks per item. Two blocks mean a
date range (first day, last day), so only single-day items and one-night items (two consecutive days with an end time
after midnight, like Museumnight 19:00-2:00) are kept. Longer ranges (exhibitions, open tours, weekly workshops) are
skipped. Start time, end time and price come from each item's detail page, fetched once per second.
The restaurant page /en/ETEN now redirects to testtafel.nl, which blocks bots (403), so dinners are not read.
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://www.mediamatic.net"
LISTS = [("events.html", "/en/events"), ("workshops.html", "/en/workshopcalendar")]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _pid(href):
    m = re.search(r"/page/(\d+)", href or "")
    return m.group(1) if m else None


def _date(day, my):
    m = re.match(r"([A-Za-z]{3})\w*\s+(\d{4})", my.strip())
    try: return datetime.date(int(m.group(2)), MON[m.group(1).lower()], int(day))
    except (AttributeError, KeyError, ValueError): return None


def _blocks(node):
    out = []
    for c in node.select("[class^=calendar-wrapper]"):
        d, my = c.select_one(".calendar__day"), c.select_one(".calendar__month__year")
        if d and my: out.append(_date(d.get_text(strip=True), my.get_text(strip=True)))
    return out


def _items(html):
    out = []
    for it in BeautifulSoup(html, "html.parser").select("article"):
        t = it.select_one(".list__item__content__title")
        a = it.find_parent("a", href=True) or it.find("a", href=True)
        if not (t and a and _pid(a["href"])): continue
        ch = it.select_one(".chapeau__header")
        ven = it.select_one(".chapeau")
        venue = ""
        if ven:
            i = ven.select_one(".glyphicon-map-marker")
            venue = re.sub(r"\s+", " ", i.find_next_sibling(string=True) or "").strip() if i is not None else ""
        sm = it.select_one(".list__item__content__summary")
        out.append({"id": _pid(a["href"]), "url": BASE + a["href"], "t": t.get_text(" ", strip=True),
                    "chapeau": ch.get_text(" ", strip=True) if ch else "", "venue": venue,
                    "dates": _blocks(it), "sum": sm.get_text(" ", strip=True) if sm else ""})
    return out


def _detail(html):
    s = BeautifulSoup(html, "html.parser")
    meta = s.select_one(".main-content--event__meta")
    h = eh = None
    if meta:
        li = meta.select_one(".meta-collection li")
        tm = re.findall(r"\d{1,2}:\d{2}", li.get_text(" ", strip=True)) if li else []
        if tm: h = tm[0].zfill(5)
        if len(tm) > 1: eh = tm[1].zfill(5)
    h1 = s.select_one("article h1")
    title = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)) if h1 else ""
    art = s.select_one("article")
    text = art.get_text(" ", strip=True) if art else ""
    price = None
    m = re.search(r"Full price\s*(?:€\s*)?(\d+(?:[.,]\d+)?)", text) or re.search(r"Tickets\s*€\s*(\d+(?:[.,]\d+)?)", text)
    if m: price = clean_price(m.group(1))
    return h, eh, price, title


def _single_day(dates, h, eh):
    """First day if the item is one day or one night, else None."""
    if not dates or None in dates or len(dates) > 2: return None
    if len(dates) == 1 or dates[0] == dates[1]: return dates[0]
    if (dates[1] - dates[0]).days == 1 and h and eh and eh < h: return dates[0]
    return None


def _cat(chapeau, t, workshop_list):
    s = (chapeau + " " + t).lower()
    if "workshop" in s or workshop_list: return "workshop"
    if re.search(r"food|dinner|menu|supper|restaurant", s): return "food"
    if re.search(r"presentation|talk|lecture|meet-a-maker|conversation", s): return "talk"
    if re.search(r"performance|theatre", s): return "theatre"
    if re.search(r"music|concert|dj\b", s): return "music"
    return "other"


def fetch(dirpath):
    """Download both list pages, then the detail page of each item that could be a single date. Returns item count."""
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    ids = set()
    for name, path in LISTS:
        out = os.path.join(dirpath, name)
        if _curl(BASE + path, out) != "200": raise RuntimeError("list page failed: " + path)
        for it in _items(open(out, errors="ignore").read()):
            if len(it["dates"]) > 2 or it["id"] in ids: continue
            if len(it["dates"]) == 2 and (it["dates"][0] is None or it["dates"][1] is None or (it["dates"][1] - it["dates"][0]).days != 1): continue
            ids.add(it["id"])
            f = os.path.join(dirpath, "detail", it["id"] + ".html")
            if _curl(it["url"], f) != "200" and os.path.exists(f): os.remove(f)
            time.sleep(1)
        time.sleep(1)
    return len(ids)


def parse_pages(pages, details, today):
    """pages: list of (name, html) with name 'events.html' or 'workshops.html'; details: {page id: html}."""
    out, seen = [], set()
    for name, html in pages:
        for it in _items(html):
            if it["id"] in seen or it["id"] not in details: continue
            seen.add(it["id"])
            h, eh, price, full = _detail(details[it["id"]])
            d = _single_day(it["dates"], h, eh)
            if not d or d < today or not it["t"]: continue
            t = it["t"]
            if t.endswith("…") and full:
                t = full.split(":", 1)[1].strip() if ":" in full[:40] else full
            e = {"t": t, "d": d.isoformat(), "v": it["venue"] or "Mediamatic Biotoop", "u": it["url"],
                 "c": _cat(it["chapeau"], it["t"], name.startswith("workshop")), "s": "mediamatic"}
            if h: e["h"] = h
            if eh: e["eh"] = eh
            if price: e["p"] = price
            if it["sum"]: e["b"] = re.sub(r"\s+", " ", it["sum"])[:220]
            k = (e["t"], e["d"], e.get("h"))
            if k in seen: continue
            seen.add(k)
            out.append(e)
    return out


def load(dirpath):
    """Read a directory written by fetch() and return (pages, details) for parse_pages()."""
    pages = [(n, open(os.path.join(dirpath, n), errors="ignore").read()) for n, _ in LISTS if os.path.exists(os.path.join(dirpath, n))]
    dd = os.path.join(dirpath, "detail")
    details = {f[:-5]: open(os.path.join(dd, f), errors="ignore").read() for f in os.listdir(dd) if f.endswith(".html")}
    return pages, details
