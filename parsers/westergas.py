"""Westergasfabriek (westergas.nl/agenda): music, comedy, kids' theatre and club nights across the cultural park.

The agenda is a server-rendered grid. Each tile has a title, a byline (date without year, optional start/end time,
venue) and a link. Date ranges (exhibitions, multi-day festivals) are skipped. Tiles without a time are kept without
"h". The list shows no prices or descriptions, so "p" and "b" are left out. robots.txt allows all.
"""
import datetime, json, re, subprocess, time
from bs4 import BeautifulSoup

BASE = "https://www.westergas.nl/agenda/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 8
MON = {"jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
DATE = re.compile(r"^[A-Za-z]{2}\s+(\d{1,2})\s+([A-Za-z]+)\s*$")
TIME = re.compile(r"^(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?$")
CANCEL = re.compile(r"geannuleerd|afgelast|cancel", re.I)


def _get(url):
    r = subprocess.run(["curl", "-sS", "-L", "-m", "45", "-A", UA, "-w", "\n%{http_code}", url], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    return code.strip(), body


def _tiles(html):
    return BeautifulSoup(html, "html.parser").select(".agenda-grid__item")


def _key(tile):
    a = tile.select_one("a[href]")
    t = tile.select_one(".event-button__text__title")
    by = tile.select_one(".event-button__text__byline")
    return (a["href"] if a else "", t.get_text(" ", strip=True) if t else "", by.get_text("|", strip=True) if by else "")


def fetch(out):
    """Download the agenda page (and further pages if the site ever paginates). Writes a JSON list of HTML strings."""
    pages, seen = [], set()
    for n in range(1, MAX_PAGES + 1):
        code, body = _get(BASE if n == 1 else f"{BASE}?paged={n}")
        if code == "403" or (code == "200" and re.search(r"cf-chl|Just a moment|captcha", body[:5000], re.I)):
            raise RuntimeError("blocked or bot challenge (HTTP %s), stopping" % code)
        if code != "200": break
        keys = {_key(t) for t in _tiles(body)}
        if not keys or keys <= seen: break      # no new events: end of list
        seen |= keys
        pages.append(body)
        time.sleep(1)
    if not pages: raise RuntimeError("no events")
    with open(out, "w") as f: json.dump(pages, f)
    return len(seen)


def _cat(title, venue):
    s = (title + " " + venue).lower()
    if "krakeling" in s: return "theatre"
    if "comedytrain" in s or re.search(r"comedy|cabaret|theater|theatre", s): return "theatre"
    if re.search(r"workshop", s): return "workshop"
    if re.search(r"markt|market|food|diner|brunch|proeverij", s): return "food"
    if "ade lab" in s or re.search(r"talk|lezing|conference", s): return "talk"
    if re.search(r"westweelde|de club|pacific|party|rave|club|\bade\b|dj", s): return "club"
    if "gashouder" in s: return "music"
    return "other"


def parse(text, today):
    out, seen = [], set()
    for html in json.loads(text):
        for tile in _tiles(html):
            url, title, by = _key(tile)
            if not title or not by or CANCEL.search(tile.get_text(" ")): continue
            parts = [p.strip() for p in by.split("|") if p.strip()]
            m = DATE.match(parts[0]) if parts else None      # a range like "Vr 23 oktober - Za 24 oktober" does not match
            if not m or m.group(2).lower()[:3] not in MON: continue
            day, mon = int(m.group(1)), MON[m.group(2).lower()[:3]]
            try: d = datetime.date(today.year, mon, day)
            except ValueError: continue
            if d < today - datetime.timedelta(days=60): d = d.replace(year=today.year + 1)
            if d < today: continue
            rest = parts[1:]
            tm = TIME.match(rest[0]) if rest else None
            if tm: rest = rest[1:]
            venue = " ".join(rest).strip() or "Westergasfabriek"
            if venue.lower() == "cultuurpark westergas": venue = "Westergasfabriek"
            k = (title, d, tm.group(1) if tm else "")
            if k in seen: continue
            seen.add(k)
            e = {"t": title, "d": d.isoformat(), "v": venue, "u": url or BASE, "c": _cat(title, venue), "s": "westergas", "nl": 1}
            if tm:
                e["h"] = tm.group(1).zfill(5)
                if tm.group(2): e["eh"] = tm.group(2).zfill(5)
            out.append(e)
    return out
