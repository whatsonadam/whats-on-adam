"""Bijlmer Parktheater (bijlmerparktheater.nl/agenda): theatre, dance, music and family shows in Amsterdam Zuidoost.

The agenda is server-rendered HTML. One card per production (li.eventCard); productions with several dates list them as
li.subshow rows, and some of those rows are tour dates in other cities, which are skipped (their venue reads
"Theater, City"). Every date row carries data-event-start="YYYY-MM-DD HH:MM:SS".

Fetching: the site redirects in a loop without cookies, so curl runs with a temporary cookie jar and -L. Later pages are
?p54_page=N (robots.txt allows ?page= and ?p*_page=; its Crawl-delay is 5 s, which is respected). If the site answers
with a challenge or an error, fetch() raises instead of trying to get around it.
The list has no description, so b is built from the credits line and the genres. Prices come from the ticket popover
(the "Standaard" fare, excluding the 1,50 online booking fee that the site lists separately).
"""
import datetime, json, os, re, subprocess, tempfile, time
from bs4 import BeautifulSoup

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://www.bijlmerparktheater.nl"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 6
PAUSE = 5          # seconds between pages, as asked by robots.txt Crawl-delay
CANCELLED = re.compile(r"geannuleerd|afgelast|vervalt|cancel+ed", re.I)
START = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})")
DUTCH = re.compile(r"\b(de|het|een|van|voor|en|met|mijn|wij|we|ons|alleen|op|is|kom|komt|terug|gaan|door|schrijven|moeder|mens|ogen)\b", re.I)


def _page_url(n):
    return BASE + "/agenda" if n == 1 else f"{BASE}/agenda?p54_page={n}"


def _get(url, jar):
    """Download one page with the cookie jar. Returns (http_code, html)."""
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    try:
        r = subprocess.run(["curl", "-sS", "-m", "45", "-L", "--max-redirs", "6", "-A", UA, "-c", jar, "-b", jar,
                            "-o", path, "-w", "%{http_code}", url], capture_output=True, text=True)
        with open(path, errors="replace") as f:
            return r.stdout.strip(), f.read()
    finally:
        os.remove(path)


def _cards(html):
    return BeautifulSoup(html, "html.parser").select("li.eventCard")


def _href(card):
    a = card.select_one("a.desc[href]")
    return a["href"] if a else None


def fetch(out):
    """Download the agenda pages into one JSON list of HTML strings. Returns the number of productions seen."""
    jar = tempfile.mktemp(suffix=".cookies")
    pages, seen = [], set()
    try:
        for n in range(1, MAX_PAGES + 1):
            code, html = _get(_page_url(n), jar)
            if code != "200":
                if n == 1: raise RuntimeError(f"bijlmerparktheater: HTTP {code}, stopping (not trying to bypass)")
                break
            hrefs = {_href(c) for c in _cards(html)} - {None}
            if n == 1 and not hrefs:
                raise RuntimeError("bijlmerparktheater: no event cards on page 1 (challenge or layout change)")
            if not hrefs - seen: break          # nothing new: the site is repeating itself
            seen |= hrefs
            pages.append(html)
            time.sleep(PAUSE)
    finally:
        if os.path.exists(jar): os.remove(jar)
    if not pages: raise RuntimeError("bijlmerparktheater: no pages")
    with open(out, "w") as f: json.dump(pages, f)
    return len(seen)


def _category(genres):
    g = " ".join(genres).lower()
    if re.search(r"lhbt|queer|pride", g): return "queer"
    if re.search(r"theater|dans|performance|cabaret|comedy|jeugd|spoken|poetry|storytelling", g): return "theatre"
    if re.search(r"lezing|debat|talk|gesprek", g): return "talk"
    if re.search(r"workshop", g): return "workshop"
    if re.search(r"feest|party|club|dj", g): return "club"
    if re.search(r"muziek|klassiek|concert|jazz|hip hop", g): return "music"
    if re.search(r"film", g): return "film"
    return "other"


def _price(block):
    """The Standaard fare from the ticket popover, else the first fare listed. None when the block shows no price."""
    for tr in block.select("table tr"):
        kind, val = tr.select_one(".pricetype"), tr.select_one("td.price")
        if kind and val and kind.get_text(strip=True).lower() == "standaard":
            return clean_price(val.get_text(" ", strip=True).replace("€", "").replace("\xa0", "").strip())
    val = block.select_one("td.price")
    if val: return clean_price(val.get_text(" ", strip=True).replace("€", "").replace("\xa0", "").strip())
    return None


def _end(block):
    e = block.select_one(".datetime .time .end") or block.select_one(".time .end")
    m = re.search(r"\d{1,2}:\d{2}", e.get_text(" ", strip=True)) if e else None
    return m.group(0).zfill(5) if m else None


def parse(text, today):
    out, seen = [], set()
    for html in json.loads(text):
        for card in _cards(html):
            t = card.select_one(".title")
            title = re.sub(r"\s+", " ", t.get_text(" ", strip=True)).strip() if t else ""
            href = _href(card)
            if not title or not href: continue
            url = href if href.startswith("http") else BASE + href
            sub = card.select_one(".subtitle")
            sub = re.sub(r"\s+", " ", sub.get_text(" ", strip=True)).strip() if sub else ""
            genres = [g.get_text(" ", strip=True) for g in card.select(".genres__link")]
            cat = _category(genres)
            english = any(re.search(r"english|engels", g, re.I) for g in genres)
            nl = 1 if (not english and DUTCH.search(title + " " + sub)) else 0
            blocks = card.select("li.subshow") or [card]
            for b in blocks:
                if b is not card and b.select_one(".venue"):
                    venue = b.select_one(".venue").get_text(" ", strip=True)
                    if "," in venue or "|" in venue: continue      # tour date in another city or theatre
                if CANCELLED.search(b.get_text(" ", strip=True)): continue
                starts = [x.get("data-event-start") or "" for x in b.select("[data-event-start]")]
                m = next((START.match(s) for s in starts if START.match(s)), None)
                if not m: continue
                try: d = datetime.date.fromisoformat(m.group(1))
                except ValueError: continue
                if d < today: continue
                key = (title, m.group(1), m.group(2))
                if key in seen: continue
                seen.add(key)
                label = " ".join(x.get_text(strip=True) for x in b.select(".status-info .label")).lower()
                st = b.select_one(".supertitle")
                e = {"t": title + (" (voorprogramma)" if st and "voorprogramma" in st.get_text().lower() else ""),
                     "d": d.isoformat(), "h": m.group(2), "v": "Bijlmer Parktheater", "u": url, "c": cat,
                     "s": "bijlmerparktheater"}
                eh = _end(b)
                if eh and eh > m.group(2): e["eh"] = eh
                if nl: e["nl"] = 1
                p = "Free" if "vrije inloop" in label else _price(b)
                if p: e["p"] = p
                desc = ". ".join(x for x in [sub.rstrip(". ") if sub != title else "", ", ".join(genres)] if x)
                if desc: e["b"] = desc[:220]
                out.append(e)
    return out
