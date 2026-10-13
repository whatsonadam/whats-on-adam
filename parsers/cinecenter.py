"""Cinecenter parser (Tricket platform). Input: raw HTML of https://www.cinecenter.nl/programma
(KEEP_HTML). The page embeds the schedule as props of an <astro-island> (DailyGridSchedule):
productions[] with screenings[] (startAtUtc, Europe/Amsterdam). Only ~10 days are on sale."""
import datetime, html, json, re
from zoneinfo import ZoneInfo

AMS = ZoneInfo("Europe/Amsterdam")
BASE = "https://www.cinecenter.nl"

def _un(v):
    if isinstance(v, dict): return {k: _un(y) for k, y in v.items()}
    if isinstance(v, list) and len(v) == 2 and v[0] in (0, 1, 3):
        return [_un(y) for y in v[1]] if v[0] == 1 else _un(v[1])
    return v

def parse(text, today):
    if "<astro-island" not in text: return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for m in re.finditer(r"<astro-island([^>]*)>", text):
        a = m.group(1)
        if "DailyGridSchedule" not in a: continue
        pm = re.search(r'props="([^"]*)"', a)
        if not pm: continue
        try: d = _un(json.loads(html.unescape(pm.group(1))))
        except Exception: continue
        for p in d.get("productions", []):
            title = (p.get("title") or "").strip()
            if not title: continue
            slug = p.get("slug")
            for s in p.get("screenings", []):
                try:
                    dt = datetime.datetime.fromisoformat(s["startAtUtc"].replace("Z", "+00:00")).astimezone(AMS)
                except Exception: continue
                if not (today <= dt.date() <= end): continue
                k = (title, dt.isoformat())
                if k in seen: continue
                seen.add(k)
                out.append({"t": title, "d": dt.date().isoformat(), "h": dt.strftime("%H:%M"),
                            "v": "Cinecenter", "u": f"{BASE}/film/{slug}" if slug else s.get("url") or f"{BASE}/programma",
                            "c": "film", "s": "cinecenter"})
    return out
