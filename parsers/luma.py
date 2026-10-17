"""Luma's public Amsterdam discover list (luma.com/amsterdam): community events, run clubs, nights out, workshops, tech meetups.

Luma's own site loads this list from a public endpoint, so no login or browser is needed. We read the first pages only
(about 40 events over the next five weeks), keep real Amsterdam events, and link every entry back to its Luma page.
Events from The Offline Club's own calendar are skipped here because the offlineclub source already has them.
"""
import datetime, json, re, subprocess
from zoneinfo import ZoneInfo

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

PLACE = "discplace-FC4SDMUVXiFtMOr"   # Luma's id for the Amsterdam discover page
API = "https://api.lu.ma/discover/get-paginated-events?discover_place_api_id=" + PLACE + "&pagination_limit=50"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
AMS = ZoneInfo("Europe/Amsterdam")
MAX_PAGES = 6
TECH = re.compile(r"\b(meetup|founder|investor|startup|go-to-market|tech|developer|apache|flink|polars|ai|careers?|invest|builders|product|fest(?:ival)? for developers|open source)\b", re.I)
OFFLINE = re.compile(r"offline club", re.I)


def fetch(out):
    """Save the entries of all pages as one JSON list. Returns the number of entries."""
    entries, cursor = [], None
    for _ in range(MAX_PAGES):
        url = API + ("&pagination_cursor=" + cursor if cursor else "")
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, url], capture_output=True, text=True)
        d = json.loads(r.stdout)
        entries += d.get("entries", [])
        cursor = d.get("next_cursor")
        if not d.get("has_more") or not cursor: break
    if not entries: raise RuntimeError("no entries")
    with open(out, "w") as f: json.dump(entries, f)
    return len(entries)


def _local(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(AMS)


def parse(text, today):
    out, seen = [], set()
    for ent in json.loads(text):
        ev = ent.get("event") or {}
        key = ev.get("api_id") or ev.get("url")
        if not key or key in seen: continue
        seen.add(key)
        geo = ev.get("geo_address_info") or {}
        if ev.get("location_type") != "offline" or geo.get("city") != "Amsterdam" or ev.get("visibility") not in (None, "public"): continue
        if OFFLINE.search((ent.get("calendar") or {}).get("name") or ""): continue
        title = re.sub(r"\s+", " ", ev.get("name") or "").strip()
        try: start = _local(ev["start_at"])
        except Exception: continue
        if not title or start.date() < today: continue
        e = {"t": title, "d": start.date().isoformat(), "h": start.strftime("%H:%M"), "v": geo.get("address") or geo.get("short_address") or "Amsterdam",
             "u": "https://luma.com/" + ev["url"], "c": "talk" if TECH.search(title) else "other", "s": "luma"}
        co = ev.get("coordinate") or {}
        if co.get("latitude"): e["la"], e["lo"] = round(co["latitude"], 6), round(co["longitude"], 6)
        tk = ent.get("ticket_info") or {}
        pr = tk.get("price") or {}
        if pr.get("cents"):
            p = clean_price(pr["cents"] / 100)
            if p: e["p"] = ("from " + p) if (pr.get("is_flexible") or tk.get("max_price")) else p
        elif tk.get("is_free"): e["p"] = "Free"
        try:
            end = _local(ev["end_at"])
            if end.date() == start.date(): e["eh"] = end.strftime("%H:%M")
        except Exception: pass
        out.append(e)
    return out
