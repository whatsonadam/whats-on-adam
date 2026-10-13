"""Shared parser for Cineville member cinemas, via Cineville's public events API
(the one cineville.nl/filmagenda itself calls): POST https://api.cineville.nl/events/search
with a venueId filter. Used by amstelveen.py, devlugt.py, thepulse.py, omval.py, bijlmerbios.py and docpaviljoen.py.

Input to parse(): the JSON saved by fetch_venue() below, or any events/search response
({"_embedded": {"events": [...]}}) or a plain list of events. Times are UTC, converted to
Europe/Amsterdam. Cineville only lists screenings roughly 1-2 weeks ahead (De Omval further)."""
import datetime, json, subprocess, time
from zoneinfo import ZoneInfo

AMS = ZoneInfo("Europe/Amsterdam")
API = "https://api.cineville.nl/events/search"
VENUE_IDS = {  # Cineville venue ids (api.cineville.nl/venues)
    "amstelveen": "db6969fc-0b17-4d8c-8b1a-6db9c7799485",
    "devlugt": "2db00d15-f8c7-4efc-ac3b-4e7fa6cfaeb0",
    "thepulse": "e2a2875a-1662-4d54-a834-634e30fe6ca2",
    "omval": "b9b8bf97-36d2-41d1-af98-ce65da2b6948",
    "bijlmerbios": "6b921d7e-4973-45a1-b6a2-20337c7aceb9",
    "docpaviljoen": "ae505216-9654-439b-8f0e-50f61288d934",
}

def fetch_venue(key, today, out_path, days=120, ua="Mozilla/5.0"):
    """Download all events of one venue (100 per page, one request per second) into out_path as a JSON list.
    Returns the number of events, or raises on a bad response."""
    end = today + datetime.timedelta(days=days + 1)
    events, after = [], None
    while True:
        body = {"productionId": {"isNull": False},
                "startDate": {"gte": today.isoformat() + "T00:00:00.000Z", "lt": end.isoformat() + "T00:00:00.000Z"},
                "venueId": {"eq": VENUE_IDS[key]}, "page": {"limit": 100}, "isHidden": {"eq": False},
                "embed": {"production": True}, "sort": {"startDate": "asc"}}
        if after: body["page"]["after"] = after
        r = subprocess.run(["curl", "-sS", "-m", "40", "-A", ua, "-X", "POST", "-H", "Content-Type: application/json",
                            "-d", json.dumps(body), API], capture_output=True, text=True)
        d = json.loads(r.stdout)
        events += d["_embedded"]["events"]
        nxt = (d.get("_links") or {}).get("next")
        if not nxt or not d["_embedded"]["events"]: break
        after = nxt["href"].split("page[after]=")[1]
        time.sleep(1.0)
    json.dump(events, open(out_path, "w"))
    return len(events)

def parse_venue(text, today, venue, key):
    try: d = json.loads(text)
    except Exception: return []
    events = d if isinstance(d, list) else (d.get("_embedded") or {}).get("events", [])
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for e in events:
        if e.get("isHidden"): continue
        p = (e.get("_embedded") or {}).get("production") or {}
        title = (p.get("title") or (e.get("productionHint") or {}).get("title") or "").strip()
        if not title: continue
        try: dt = datetime.datetime.fromisoformat(e["startDate"].replace("Z", "+00:00")).astimezone(AMS)
        except Exception: continue
        if not (today <= dt.date() <= end): continue
        k = (title, dt.isoformat())
        if k in seen: continue
        seen.add(k)
        slug = p.get("slug")
        url = e.get("ticketingUrl") or (f"https://www.cineville.nl/nl-NL/films/{slug}" if slug else "https://www.cineville.nl/nl-NL/filmagenda")
        out.append({"t": title, "d": dt.date().isoformat(), "h": dt.strftime("%H:%M"), "v": venue,
                    "u": url, "c": "film", "s": key})
    return out
