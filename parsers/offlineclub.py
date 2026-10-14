"""The Offline Club, Amsterdam chapter: events from their public Luma calendar (luma.com/theofflineclubamsterdam).

The calendar page carries its events as JSON inside the page (__NEXT_DATA__), so no browser is needed.
Only Amsterdam events are kept (the retreats in Hooghalen and online events are skipped), and
members-only events are left out because the public cannot join them.
"""
import datetime, json, re, subprocess
from zoneinfo import ZoneInfo

URL = "https://luma.com/theofflineclubamsterdam"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
AMS = ZoneInfo("Europe/Amsterdam")
WORKSHOP = re.compile(r"\b(workshop|craft|terrarium|reflection)\b", re.I)


def fetch(out):
    r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, "-o", out, "-w", "%{http_code}", URL], capture_output=True, text=True)
    return r.stdout.strip()


def _events(o):
    if isinstance(o, dict):
        if "start_at" in o and "name" in o: yield o
        for v in o.values(): yield from _events(v)
    elif isinstance(o, list):
        for v in o: yield from _events(v)


def _local(iso):
    return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(AMS)


def parse(text, today):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not m: return []
    out, seen = [], set()
    for ev in _events(json.loads(m.group(1))):
        key = ev.get("api_id") or ev.get("url")
        if key in seen: continue
        seen.add(key)
        geo = ev.get("geo_address_info") or {}
        if ev.get("location_type") != "offline" or geo.get("city") != "Amsterdam": continue
        title = re.sub(r"\s+", " ", ev["name"]).strip()
        if re.match(r"members[- ]only", title, re.I): continue
        try: start = _local(ev["start_at"])
        except Exception: continue
        if start.date() < today: continue
        e = {"t": title, "d": start.date().isoformat(), "h": start.strftime("%H:%M"), "v": geo.get("address") or "The Offline Club",
             "u": "https://luma.com/" + ev["url"], "c": "workshop" if WORKSHOP.search(title) else "community", "s": "offlineclub"}
        if ev.get("end_at"):
            try:
                end = _local(ev["end_at"])
                if end.date() == start.date(): e["eh"] = end.strftime("%H:%M")
            except Exception: pass
        out.append(e)
    return out
