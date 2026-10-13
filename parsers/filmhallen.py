"""Filmhallen parser. Input: JSON from https://filmhallen.nl/fk-feed/agenda (plain curl works).
Dict slug -> film; film['times'] = screenings with program_start 'YYYYMMDDHHMM' (local time).
VR installations (room name starting 'VR', ~1000 slot rows) are skipped: not film screenings."""
import datetime, html, json

def parse(text, today):
    try: d = json.loads(text)
    except Exception: return []
    if not isinstance(d, dict): return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for slug, f in d.items():
        if not isinstance(f, dict): continue
        title = html.unescape(f.get("title") or "").strip()
        if not title: continue
        sub = html.unescape(f.get("subtitle") or "").strip()
        url = f.get("permalink") or f"https://filmhallen.nl/films/{slug}/"
        for t in f.get("times") or []:
            if (t.get("location") or "").startswith("VR"): continue
            ps = str(t.get("program_start") or "")
            try: dt = datetime.datetime.strptime(ps, "%Y%m%d%H%M")
            except ValueError: continue
            if not (today <= dt.date() <= end): continue
            k = (slug, ps, t.get("location"))
            if k in seen: continue
            seen.add(k)
            e = {"t": title, "d": dt.date().isoformat(), "h": dt.strftime("%H:%M"),
                 "v": "Filmhallen", "u": url, "c": "film", "s": "filmhallen"}
            if sub: e["b"] = sub[:120]
            if t.get("ticket_status") == "sold-out": e["p"] = "Sold out"
            out.append(e)
    return out
