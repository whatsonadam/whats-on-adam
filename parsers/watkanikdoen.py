"""Wat kan ik doen? (watkanikdoen.nl), the Dutch demonstration agenda, Amsterdam actions only.

The site is open source and has a public JSON API (/api/v1/acties). The list is oldest first (about 780 actions, 15 per
page), so we read pages from the last one backwards until a whole page is in the past, then fetch each upcoming
action's own record for its place and description. An action counts as Amsterdam when its place says so; when the
place is still unknown ("Nog niet bekend"), when the title or text says Amsterdam. Dutch text is marked tl=1 for
translation, and the description is cut to a short blurb.
"""
import datetime, json, os, re, subprocess, time
from bs4 import BeautifulSoup

API = "https://watkanikdoen.nl/api/v1/acties"
UA = "whatsonadam-agenda (non-commercial hobby site; github.com/whatsonadam/whats-on-adam)"
MAX_BACK = 8        # list pages to read backwards from the end, at most
HORIZON = 150       # days ahead to keep
AMS = re.compile(r"\bamsterdam\b", re.I)
UNKNOWN = re.compile(r"^\W*(nog )?(niet )?onbekend\W*$|^\W*nog niet bekend\W*$|^\W*$", re.I)
# Places the site has not filled in yet but the organisers have announced elsewhere (checked by hand). Remove once the site has them.
PLACE_OVERRIDES = {
    "de-rode-lijn-voorbij-8-november": "Museumplein, Amsterdam",   # Amnesty's page and Aktie Agenda both say Museumplein
}


def _get(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-H", "Accept: application/json", "-o", out, "-w", "%{http_code}", url],
                       capture_output=True, text=True)
    return r.stdout.strip()


def _json(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def fetch(dirpath, today=None):
    """Download the last list pages and the records of upcoming actions into dirpath. Returns how many upcoming actions."""
    today = today or datetime.date.today()
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    for root, _, files in os.walk(dirpath):
        for f in files: os.remove(os.path.join(root, f))
    first = os.path.join(dirpath, "first.json")
    if _get(API, first) != "200": raise RuntimeError("actions API did not answer")
    last = ((_json(first) or {}).get("meta") or {}).get("last_page")
    os.remove(first)
    if not last: raise RuntimeError("actions API gave no page count")
    upcoming = []
    for p in range(last, max(0, last - MAX_BACK), -1):
        out = os.path.join(dirpath, f"p{p:03d}.json")
        if _get(f"{API}?page={p}", out) != "200": os.remove(out); break
        items = (_json(out) or {}).get("data") or []
        upcoming += [x["slug"] for x in items if x.get("start_date", "") >= today.isoformat()]
        if items and all(x.get("start_date", "") < today.isoformat() for x in items): break
        time.sleep(0.5)
    for slug in dict.fromkeys(upcoming):
        _get(f"{API}/{slug}", os.path.join(dirpath, "detail", slug + ".json"))
        time.sleep(0.4)
    return len(upcoming)


def _text(html):
    t = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", t).strip()


def _blurb(text, limit=300):
    if len(text) <= limit: return text
    cut = text[:limit]
    m = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:m + 1] if m > 100 else cut.rsplit(" ", 1)[0] + "…"


def _hhmm(s):
    m = re.match(r"(\d{1,2}):(\d{2})", s or "")
    return None if not m or (m.group(1), m.group(2)) == ("00", "00") else f"{int(m.group(1)):02d}:{m.group(2)}"


def parse_pages(pages, details, today):
    """pages: list of list-page JSON (already loaded); details: {slug: record JSON} for upcoming actions."""
    out, seen = [], set()
    end = today + datetime.timedelta(days=HORIZON)
    for page in pages:
        for item in (page or {}).get("data") or []:
            try: d = datetime.date.fromisoformat(item["start_date"])
            except Exception: continue
            if d < today or d > end or item["slug"] in seen: continue
            rec = (details.get(item["slug"]) or {}).get("data")
            if not rec: continue
            seen.add(item["slug"])
            place = (rec.get("location_human") or "").strip()
            body = _text(rec.get("body"))
            if (not place or UNKNOWN.match(place)) and item["slug"] in PLACE_OVERRIDES:
                place = PLACE_OVERRIDES[item["slug"]]
            if place and not UNKNOWN.match(place):
                if not AMS.search(place): continue
                venue = place
            else:
                if not AMS.search(item["title"] + " " + body): continue
                venue = "Amsterdam"
            e = {"t": re.sub(r"\s+", " ", item["title"]).strip(), "d": d.isoformat(), "v": venue,
                 "u": rec.get("link") or item.get("link"), "c": "protest", "s": "watkanikdoen", "tl": 1}
            h = _hhmm(item.get("start_time"))
            if h:
                e["h"] = h
                eh = _hhmm(item.get("end_time"))
                if eh and eh != h and item.get("end_date") == item["start_date"]: e["eh"] = eh
            if body: e["b"] = _blurb(body)
            out.append(e)
    return out
