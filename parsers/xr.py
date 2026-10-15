"""Extinction Rebellion Nederland events (extinctionrebellion.nl/events), Amsterdam only.

The list is national (about 90 events over 9 pages, /events/ and /events/page/N/) and grouped by day. Each entry gives
title, tagline and a details line such as "19:00 - 21:30 • Arnhem • Nederlands gesproken", but the place is missing on
about 4 in 10 entries. Those get one request to their own event page, where the place sits under the date and time.
An event counts as Amsterdam when its place says so; with no place at all, when the organising group's name does.
Online events are skipped. Spoken language is shown in the description; protests are never hidden by the
English-friendly filter (see build.py). Dutch text is marked tl=1 for translation.
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _dates import find_dates
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates

BASE = "https://extinctionrebellion.nl/events/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 15
AMS = re.compile(r"\bamsterdam\b", re.I)
TIMES = re.compile(r"(\d{1,2}):(\d{2})")
LANG = re.compile(r"^(\w+) gesproken$", re.I)
LANG_EN = {"nederlands": "Dutch", "engels": "English", "duits": "German", "frans": "French", "spaans": "Spanish"}
SKIP_PLACE = re.compile(r"^(online|digitaal|nog niet bekend)$", re.I)


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _entries(html, today):
    """List entries of one page: dicts with date, title, url, tagline and the bits of the details line."""
    s = BeautifulSoup(html, "html.parser")
    out = []
    for h3 in s.select("h3.d-none.d-lg-block"):
        dates = find_dates(h3.get_text(" ", strip=True), today)
        row = h3.find_parent("div", class_="row")
        body = row.select_one("div.col-lg-10") if row else None
        if not dates or not body: continue
        for col in body.select("div.col-lg-5"):
            a = col.find("a", href=True)
            h4 = col.find("h4")
            if not a or not h4: continue
            ps = [p.get_text(" ", strip=True) for p in col.find_all("p")]
            parts = [x.strip() for x in (ps[1] if len(ps) > 1 else "").split("•") if x.strip()]
            out.append({"d": dates[0], "t": re.sub(r"\s+", " ", h4.get_text(" ", strip=True)), "u": a["href"],
                        "tag": ps[0] if ps else "", "parts": parts})
    return out


def _detail(html):
    """(place, organiser) from an event page: the place is the line after the time, if it is not a language or price."""
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "noscript", "svg", "header", "footer", "nav"]): t.decompose()
    lines = [l.strip() for l in s.get_text("\n").splitlines() if l.strip()]
    place = org = None
    for i, l in enumerate(lines):
        if re.fullmatch(r"\d{1,2} [a-z]+ \d{4}", l, re.I):
            for x in lines[i + 1:i + 4]:
                if re.search(r"\d{1,2}:\d{2}", x) or LANG.match(x) or x.lower().startswith("prijs") or x.lower().startswith("aanmelden"): continue
                place = x; break
            break
    for i, l in enumerate(lines):
        if l == "Organisatie" and i + 1 < len(lines): org = lines[i + 1]; break
    return place, org


def _needs_detail(ent):
    return not any(not TIMES.match(p) and not LANG.match(p) for p in ent["parts"])


def fetch(dirpath, today=None):
    """Download list pages into dirpath/pNN.html and the event pages with no place into dirpath/detail/. Returns event count."""
    today = today or datetime.date.today()
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    for root, _, files in os.walk(dirpath):
        for f in files: os.remove(os.path.join(root, f))
    ents = []
    for p in range(1, MAX_PAGES + 1):
        out = os.path.join(dirpath, f"p{p:02d}.html")
        code = _curl(BASE if p == 1 else f"{BASE}page/{p}/", out)
        if code != "200":
            if os.path.exists(out): os.remove(out)
            if p == 1: raise RuntimeError(f"events page returned {code}")
            break
        found = _entries(open(out, errors="ignore").read(), today)
        if not found:
            os.remove(out); break
        ents += found
        time.sleep(1.0)
    seen = set()
    for ent in ents:
        if not _needs_detail(ent) or ent["u"] in seen: continue
        seen.add(ent["u"])
        _curl(ent["u"], os.path.join(dirpath, "detail", _slug(ent["u"]) + ".html"))
        time.sleep(0.5)
    return len(ents)


def parse_pages(pages, details, today):
    """pages: list of list-page HTML; details: {event slug: event page HTML} for entries that had no place."""
    out, seen = [], set()
    for html in pages:
        for ent in _entries(html, today):
            if ent["d"] < today: continue
            place = next((p for p in ent["parts"] if not TIMES.match(p) and not LANG.match(p)), None)
            org = None
            if not place and _slug(ent["u"]) in details:
                place, org = _detail(details[_slug(ent["u"])])
            if place and SKIP_PLACE.match(place): continue
            if not AMS.search(place or "") and not (not place and org and AMS.search(org)): continue
            key = (ent["d"], ent["t"].lower(), ent["u"])
            if key in seen: continue
            seen.add(key)
            e = {"t": ent["t"], "d": ent["d"].isoformat(), "v": place or "Amsterdam", "u": ent["u"], "c": "protest", "s": "xr", "tl": 1}
            tm = next((TIMES.findall(p) for p in ent["parts"] if TIMES.match(p)), [])
            if tm:
                e["h"] = f"{int(tm[0][0]):02d}:{tm[0][1]}"
                if len(tm) > 1 and tm[1] != tm[0]: e["eh"] = f"{int(tm[1][0]):02d}:{tm[1][1]}"
            lang = next((LANG.match(p).group(1).lower() for p in ent["parts"] if LANG.match(p)), None)
            bits = [ent["tag"]] if ent["tag"] else []
            if lang and LANG_EN.get(lang): bits.append(f"Spoken in {LANG_EN[lang]}.")
            if org: bits.append(f"Organised by {org}.")
            if bits: e["b"] = " ".join(bits)
            out.append(e)
    return out
