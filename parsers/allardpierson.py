"""Allard Pierson (allardpierson.nl/agenda): lectures, live research sessions, performances and weekly drop-in talks.

The agenda page lists cards linking to /agenda/<slug>. Cards with a single day ("21 oktober") or a weekly rhythm
("Elke woensdag, 14.00 - 15.00") are kept; exhibitions and date ranges are skipped (separate Exhibitions tab). Each
kept card's detail page gives Datum, Tijd and Prijs, so it is fetched once (one per second). Weekly items expand to
the next 8 weeks, minus any weekday named in an "afwezig op woensdag 21 oktober" style note.
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://www.allardpierson.nl"
LIST = BASE + "/agenda/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MON = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
       "september": 9, "oktober": 10, "november": 11, "december": 12}
DAYS = {"maandag": 0, "dinsdag": 1, "woensdag": 2, "donderdag": 3, "vrijdag": 4, "zaterdag": 5, "zondag": 6}
MONRX = "|".join(MON)
SINGLE = re.compile(rf"^(\d{{1,2}})\s+({MONRX})$", re.I)
WEEKLY = re.compile(r"Elke\s+(" + "|".join(DAYS) + r"),?\s*(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})", re.I)
TIME = re.compile(r"(\d{1,2})[.:](\d{2})(?:\s*-\s*(\d{1,2})[.:](\d{2}))?")
WEEKS = 8


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _cards(html):
    """Yield (url, text) for each unique agenda card that is a single day or weekly item."""
    s = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in s.select('a[href^="/agenda/"]'):
        href = a["href"].split("?")[0].rstrip("/")
        slug = _slug(href)
        if slug in ("agenda", "archief") or href.count("/") != 2 or slug in seen: continue
        text = a.get_text(" ", strip=True)
        if WEEKLY.search(text) or SINGLE.match(text.split(" ", 2)[0] + " " + text.split(" ", 2)[1] if len(text.split(" ", 2)) > 1 else ""):
            seen.add(slug)
            out.append((BASE + href, text))
    return out


def fetch(dirpath):
    """Download the agenda page and the detail page of each single-day or weekly card. Returns the card count."""
    os.makedirs(dirpath, exist_ok=True)
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    path = os.path.join(dirpath, "list.html")
    if _curl(LIST, path) != "200": raise RuntimeError("agenda not reachable")
    cards = _cards(open(path, errors="ignore").read())
    if not cards: raise RuntimeError("no cards")
    for u, _ in cards:
        time.sleep(1)
        _curl(u, os.path.join(dirpath, "detail", _slug(u) + ".html"))
    return len(cards)


def _detail(html):
    s = BeautifulSoup(html, "html.parser")
    lines = list(s.get_text("\n", strip=True).split("\n"))
    def after(label):
        for i, l in enumerate(lines):
            if l == label and i + 1 < len(lines): return lines[i + 1]
    body = s.get_text(" ", strip=True)
    absent = set()
    for m in re.finditer(rf"afwezig[^.]*?\b(\d{{1,2}})\s+({MONRX})", body, re.I):
        absent.add((MON[m.group(2).lower()], int(m.group(1))))
    desc = s.select_one('meta[name="description"]')
    kind = ""
    for l in lines:
        if re.match(r"^(Lezing|Rondleiding|Workshop|Optreden|Presentatie|Symposium|Voor kinderen|Schouw|Cursus)", l, re.I): kind = l; break
    return {"date": after("Datum"), "time": after("Tijd"), "price": after("Prijs"),
            "desc": (desc.get("content") if desc else "") or "", "absent": absent, "kind": kind, "h1": (s.find("h1").get_text(" ", strip=True) if s.find("h1") else "")}


def _category(text):
    t = text.lower()
    if re.search(r"optreden|concert|liveset|muziek", t): return "music"
    if re.search(r"workshop|cursus|atelier", t): return "workshop"
    if re.search(r"lezing|symposium|presentatie|vindplaats live|conservator|onderzoek|gesprek", t): return "talk"
    return "other"


def _price(raw):
    if not raw: return None
    if re.search(r"gratis|free|vrije toegang", raw, re.I): return "Free"
    if re.search(r"museumticket|museumkaart", raw, re.I): return "With museum ticket"
    if "€" in raw: return clean_price(raw)
    return None


def _hm(h, m): return f"{int(h):02d}:{m}"


def parse_pages(pages, details, today):
    out, seen = [], set()
    for html in pages:
        for url, text in _cards(html):
            slug = _slug(url)
            if slug not in details or slug in seen: continue
            seen.add(slug)
            info = _detail(details[slug])
            title = re.sub(r"\s+", " ", text).strip()
            wk = WEEKLY.search(text)
            if wk:
                title = re.sub(r"^Elke\s+\w+,\s*[\d.: -]+\s*", "", title).strip()
            else:
                title = re.sub(rf"^\d{{1,2}}\s+({MONRX})\s*", "", title, flags=re.I).strip()
            title = title or info["h1"]
            if not title: continue
            tm = TIME.search(info["time"] or "")
            if wk: tm = wk
            if not tm: continue
            h = _hm(tm.group(2 if wk else 1), tm.group(3 if wk else 2)) if wk else _hm(tm.group(1), tm.group(2))
            eh = None
            if wk: eh = _hm(wk.group(4), wk.group(5))
            elif tm.group(3): eh = _hm(tm.group(3), tm.group(4))
            dates = []
            if wk:
                wd = DAYS[wk.group(1).lower()]
                d = today + datetime.timedelta(days=(wd - today.weekday()) % 7)
                dates = [d + datetime.timedelta(weeks=i) for i in range(WEEKS)]
                dates = [x for x in dates if (x.month, x.day) not in info["absent"]]
            else:
                m = SINGLE.match(" ".join(text.split(" ")[:2]))
                try:
                    d = datetime.date(today.year, MON[m.group(2).lower()], int(m.group(1)))
                    if d < today - datetime.timedelta(days=60): d = d.replace(year=today.year + 1)
                    dates = [d]
                except (ValueError, AttributeError): continue
            c = _category(" ".join([info["kind"], title, info["desc"]]))
            p = _price(info["price"])
            b = re.sub(r"\s+", " ", info["desc"]).strip()
            if len(b) > 220: b = b[:217].rsplit(" ", 1)[0] + "..."
            for d in dates:
                if d < today: continue
                e = {"t": title, "d": d.isoformat(), "h": h, "v": "Allard Pierson", "u": url, "c": c, "s": "allardpierson", "nl": 1}
                if eh: e["eh"] = eh
                if p: e["p"] = p
                if b: e["b"] = b
                out.append(e)
    return out
