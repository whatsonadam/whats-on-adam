"""Fill in missing start time, end time and price from an event's own page.

Some venue lists only give a date and title (or a start time), while the event's own page says
"DOORS: 21:00 UNTIL 01:00", "Open: 19:30 - 01:00 hrs" or "18:00 - 01:00" and "Tickets: € 10".
fetch.py saves those pages for the sources in SOURCES (at most MAX per source, one per second);
build.py then calls enrich() on that source's events. Only empty fields are filled, never overwritten.
"""
import hashlib, os, re
from html import unescape

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

SOURCES = ["garagenoord", "skatecafe", "ot301", "amsterdamalternative", "tolhuistuin", "parallel", "radion", "nieuweanita"]
MAX = 45
PAUSE = {"garagenoord": 4}     # seconds between pages; Garage Noord answers 429 when asked faster
T = r"(\d{1,2})[:.](\d{2})"
RANGE = re.compile(T + r"\s*(?:u(?:ur)?|h(?:rs)?)?\s*(?:-|–|—|to|until|till|tot)\s*" + T, re.I)
DOORS = re.compile(r"(?:doors?|deur(?:en)?|open|start|aanvang)\s*:?\s*" + T + r"(?:[^0-9]{0,25}?(?:until|till|tot|close|sluit|end|einde)\s*:?\s*" + T + r")?", re.I)
PRICE = re.compile(r"(?:tickets?|entr(?:y|ance|ee)|prijs|price|kaarten)\s*:?\s*(?:vanaf |from )?€\s*(\d+(?:[.,]\d{1,2})?)", re.I)
FREE = re.compile(r"\b(free entry|free entrance|gratis entree|vrije toegang|entree gratis|toegang gratis)\b", re.I)


def fname(url):
    return hashlib.md5(url.encode()).hexdigest()[:16] + ".html"


def text(html):
    x = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", x)))


def _hm(h, m):
    h = int(h)
    return f"{h:02d}:{m}" if 0 <= h <= 24 else None


def extract(html, start=None):
    """Return (h, eh, price) found on the page, each None when not found."""
    x = text(html)
    h = eh = price = None
    m = DOORS.search(x)
    if m:
        h = _hm(m.group(1), m.group(2))
        if m.group(3): eh = _hm(m.group(3), m.group(4))
    ranges = [(_hm(r.group(1), r.group(2)), _hm(r.group(3), r.group(4))) for r in RANGE.finditer(x)]
    pick = next((r for r in ranges if r[0] == start), None) if start else None
    pick = pick or (ranges[0] if ranges else None)
    if pick: h, eh = h or pick[0], eh or pick[1]
    if eh == "24:00": eh = "00:00"
    if h and eh and eh == h: eh = None
    p = PRICE.search(x)
    if p:
        price = clean_price(p.group(1))
    elif FREE.search(x):
        price = "Free"
    return h, eh, price


def enrich(events, ddir):
    if not os.path.isdir(ddir): return 0
    n = 0
    for e in events:
        f = os.path.join(ddir, fname(e.get("u") or ""))
        if not e.get("u") or not os.path.exists(f): continue
        h, eh, price = extract(open(f, errors="ignore").read(), e.get("h"))
        changed = False
        if h and not e.get("h"): e["h"] = h; changed = True
        if eh and not e.get("eh") and e.get("h") and eh != e["h"]: e["eh"] = eh; changed = True
        if price and not e.get("p"): e["p"] = price; changed = True
        n += changed
    return n
