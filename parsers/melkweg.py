"""Melkweg (melkweg.nl/en/agenda): concerts, club nights and festivals at Melkweg.

The agenda page embeds every upcoming event as JSON ("initialEvents"), with start time in UTC, an end time for some
nights, tags and a sold-out flag. Films are read by melkwegcinema.py and the Expo by the exhibitions sources, so both
are skipped here. Ticket prices are only on each event's own page ("ticketPrices"), so the detail page of every event
in the next DAYS days is fetched once (one per second). Melkweg asks for a membership on top of most tickets; the
price shown is the regular ticket price, with "+ membership" when the site says one is required.
"""
import datetime, json, os, re, subprocess, time
from zoneinfo import ZoneInfo

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://www.melkweg.nl"
LIST = BASE + "/en/agenda/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
AMS = ZoneInfo("Europe/Amsterdam")
DAYS = 60
SKIP = {"Film", "Expositie"}


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-L", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _events(html):
    i = html.find('"initialEvents":')
    if i < 0: return []
    try:
        arr, _ = json.JSONDecoder().raw_decode(html[i + len('"initialEvents":'):])
    except ValueError:
        return []
    return [a.get("attributes") or {} for a in arr if isinstance(a, dict)]


def _slug(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _local(iso):
    try:
        return datetime.datetime.fromisoformat(re.sub(r"\.\d+", "", iso[:26]).replace("Z", "") + "+00:00").astimezone(AMS)
    except (ValueError, AttributeError):
        return None


def fetch(dirpath, today=None):
    """Download the agenda page and the detail page of each event in the next DAYS days. Returns the event count."""
    today = today or datetime.date.today()
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    path = os.path.join(dirpath, "list.html")
    if _curl(LIST, path) != "200": raise RuntimeError("melkweg agenda not reachable")
    evs = _events(open(path, errors="ignore").read())
    if not evs: raise RuntimeError("melkweg: no events in page (layout change?)")
    n = 0
    for a in evs:
        st = _local(a.get("startTime") or a.get("startDate") or "")
        if not st or a.get("profile") in SKIP or not a.get("url"): continue
        if not (today <= st.date() <= today + datetime.timedelta(days=DAYS)): continue
        _curl(BASE + a["url"], os.path.join(dirpath, "detail", _slug(a["url"]) + ".html"))
        n += 1
        time.sleep(1)
    return n


def _price(html):
    m = re.search(r'"ticketPrices":(\{.*?\})\s*,\s*"', html)
    if not m:
        i = html.find('"ticketPrices":')
        if i < 0: return None
        try: tp, _ = json.JSONDecoder().raw_decode(html[i + len('"ticketPrices":'):])
        except ValueError: return None
    else:
        try: tp = json.loads(m.group(1))
        except ValueError:
            try: tp, _ = json.JSONDecoder().raw_decode(html[html.find('"ticketPrices":') + len('"ticketPrices":'):])
            except ValueError: return None
    shown = [t for t in tp.values() if isinstance(t, dict) and t.get("show") and t.get("price")]
    if not shown: return None
    main = next((t for t in shown if t.get("primary")), shown[0])
    p = clean_price(str(main["price"]).replace("€", "").replace("\xa0", "").strip())
    if p and p != "Free" and main.get("membership_required"): p += " + membership"
    return p


def _cat(a):
    prof, tags = a.get("profile") or "", " ".join(a.get("tags") or []).lower()
    if prof == "Clubnacht": return "club"
    if "comedy" in tags: return "theatre"
    if "lgbt" in tags or "queer" in tags: return "queer" if prof != "Concert" else "music"
    return "music"


def parse_pages(list_html, details, today):
    out, seen = [], set()
    for a in _events(list_html):
        if a.get("profile") in SKIP or not a.get("url") or not a.get("name"): continue
        if a.get("isCancelled") or a.get("isPrivateEvent") or a.get("isPublished") is False: continue
        st = _local(a.get("startTime") or a.get("startDate") or "")
        if not st or st.date() < today: continue
        if a.get("isMultiDayEvent"): continue
        key = (a["name"], st.isoformat())
        if key in seen: continue
        seen.add(key)
        title = re.sub(r"\s+", " ", a["name"]).strip()
        e = {"t": title, "d": st.date().isoformat(), "h": st.strftime("%H:%M"), "v": "Melkweg",
             "u": BASE + a["url"], "c": _cat(a), "s": "melkweg"}
        en = _local(a.get("endDate") or "")
        if en and en > st and en - st < datetime.timedelta(hours=14): e["eh"] = en.strftime("%H:%M")
        det = details.get(_slug(a["url"]))
        p = _price(det) if det else None
        if a.get("isSoldOut"): e["so"] = 1
        if p: e["p"] = p
        bits = [x for x in [a.get("subtitle"), a.get("artists"), ", ".join((a.get("tags") or [])[:3])] if x]
        if bits: e["b"] = ". ".join(b.strip().rstrip(".") for b in bits)[:220]
        out.append(e)
    return out


def load(dirpath):
    lp = os.path.join(dirpath, "list.html")
    lh = open(lp, errors="ignore").read() if os.path.exists(lp) else ""
    dd = os.path.join(dirpath, "detail")
    det = {f[:-5]: open(os.path.join(dd, f), errors="ignore").read() for f in os.listdir(dd) if f.endswith(".html")} if os.path.isdir(dd) else {}
    return lh, det
