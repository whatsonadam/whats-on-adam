"""The Movies parser. Input: JSON from https://themovies.nl/fk-feed/agenda (the feed the agenda page loads;
dict slug -> film with a 'times' list, program_start = YYYYMMDDHHMM local time). Note: use the host
themovies.nl (www.the-movies.nl is refused by the sandbox proxy and redirects there anyway)."""
import datetime, json

def parse(text, today):
    try: data = json.loads(text)
    except ValueError: return []
    if not isinstance(data, dict): return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for slug, m in data.items():
        if not isinstance(m, dict): continue
        title = (m.get("title") or "").strip()
        if not title: continue
        for t in m.get("times") or []:
            ps = str(t.get("program_start") or "")
            if len(ps) < 12 or not ps[:12].isdigit(): continue
            try: d = datetime.date(int(ps[:4]), int(ps[4:6]), int(ps[6:8]))
            except ValueError: continue
            if d < today or d > end: continue
            h = f"{ps[8:10]}:{ps[10:12]}"
            k = (t.get("provider_id") or t.get("child_id"), title, d, h)
            if k in seen: continue
            seen.add(k)
            u = m.get("permalink") or (f"https://themovies.nl/tickets/{t['provider_id']}" if t.get("provider_id") else "https://themovies.nl/agenda/")
            out.append({"t": title, "d": d.isoformat(), "h": h, "v": "The Movies", "u": u, "c": "film", "s": "themovies"})
    out.sort(key=lambda e: (e["d"], e["h"]))
    return out
