"""Melkweg Cinema parser. Input: raw HTML (KEEP_HTML) of https://www.melkweg.nl/nl/agenda.
The page is Next.js; the whole agenda (all profiles, ~1 year) is in <script id="__NEXT_DATA__">
as initialEvents. Cinema screenings are the events with profile 'Film'. Times are UTC, converted
to Europe/Amsterdam. (A raw JSON string of the same structure is accepted too.)"""
import datetime, json, re
from zoneinfo import ZoneInfo

AMS = ZoneInfo("Europe/Amsterdam")
BASE = "https://www.melkweg.nl"

def _events(text):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    try: d = json.loads(m.group(1) if m else text)
    except Exception: return []
    if "props" in d: d = d["props"]
    try: content = d["pageProps"]["pageData"]["attributes"]["content"]
    except Exception: return []
    for c in content:
        ev = (c.get("attributes") or {}).get("initialEvents")
        if ev: return ev
    return []

def parse(text, today):
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for e in _events(text):
        a = e.get("attributes") or {}
        if a.get("profile") != "Film": continue
        if a.get("isCancelled") or a.get("isMovedToNewDate") or a.get("isPrivateEvent") or a.get("isPublished") is False: continue
        title = (a.get("name") or "").strip()
        ts = a.get("startTime") or a.get("startDate")
        if not title or not ts: continue
        try: dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(AMS)
        except Exception: continue
        if not (today <= dt.date() <= end): continue
        url = a.get("url") or ""
        k = (url or title, dt.isoformat())
        if k in seen: continue
        seen.add(k)
        ev = {"t": title, "d": dt.date().isoformat(), "h": dt.strftime("%H:%M"), "v": "Melkweg Cinema",
              "u": BASE + url if url.startswith("/") else (url or BASE + "/nl/agenda"), "c": "film", "s": "melkwegcinema"}
        sub = (a.get("subtitle") or "").strip()
        if sub: ev["b"] = sub[:120]
        if a.get("isSoldOut"): ev["p"] = "Sold out"
        out.append(ev)
    return out
