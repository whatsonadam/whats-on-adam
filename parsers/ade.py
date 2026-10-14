"""Amsterdam Dance Event: the festival programme from ADE's own public listing (JSON, one file per page).

Each item has a title, subtitle, start and end, venue, a category string and a soldOut flag. ADE events
carry 'ade': 1 so the site can show them in the temporary ADE tab, and 'so': 1 when sold out.
"""
import datetime

def _cat(cats, title):
    s = (cats + " " + title).lower()
    if any(k in s for k in ("conference", "panel", "talk", "keynote", "lecture", "meetup", "networking", "pro ")): return "talk"
    if any(k in s for k in ("workshop", "masterclass", "lab ", "class", "yoga", "breathwork")): return "workshop"
    if any(k in s for k in ("exhibition", "installation", "expo")): return "exhibition"
    if any(k in s for k in ("concert", "live", "record store", "listening", "orchestra", "choir")): return "music"
    return "club"

GENRES = (("Techno", ("techno",)), ("House", ("house",)), ("Trance", ("trance",)), ("Disco", ("disco",)),
          ("Melodic", ("melodic",)), ("Ambient", ("ambient", "chillout", "listening")))


def _kind(cats, title):
    s = cats.lower()
    if "exhibition" in s or "installation" in s: return "Exhibitions"
    if "wellbeing" in s or "sports" in s: return "Wellbeing and sports"
    if "workshop" in s or "masterclass" in s: return "Workshops"
    if "network" in s or "talk" in s or "conference" in s or "panel" in s: return "Talks and networking"
    if "club night" in s or "nighttime" in s or "all night" in s: return "Club night"
    if "live" in s: return "Live"
    return {"talk": "Talks and networking", "workshop": "Workshops", "exhibition": "Exhibitions",
            "music": "Live"}.get(_cat(cats, title), "Club night")


def _genres(cats):
    s = cats.lower()
    return [g for g, ks in GENRES if any(k in s for k in ks)]


def parse_pages(pages, today):
    out, seen = [], set()
    for page in pages:
        for v in page.get("data", []):
            try:
                s = v["start_date_time"]["date"]; e = v["end_date_time"]["date"]
                d = datetime.date.fromisoformat(s[:10]); ed = datetime.date.fromisoformat(e[:10])
            except Exception:
                continue
            if d < today and ed < today: continue
            key = (v.get("id"), d)
            if key in seen: continue
            seen.add(key)
            cats = v.get("categories") or ""
            ev = {"t": (v.get("title") or "").strip(), "d": d.isoformat(), "v": (v.get("venue") or {}).get("title") or "",
                  "u": v.get("url"), "c": _cat(cats, v.get("title") or ""), "s": "ade", "ade": 1}
            ev["ak"] = _kind(cats, v.get("title") or "")
            if _genres(cats): ev["ag"] = _genres(cats)
            if v.get("subtitle"): ev["b"] = v["subtitle"].strip()[:120]
            if v.get("soldOut"): ev["so"] = 1
            hs, he = s[11:16], e[11:16]
            if v.get("show_start_date_time") and hs not in ("", "00:00"):
                ev["h"] = hs
                if he and he not in ("23:59", hs) and ed == d: ev["eh"] = he
            if (ed - d).days >= 2: ev["ed"] = ed.isoformat()
            out.append(ev)
    return out
