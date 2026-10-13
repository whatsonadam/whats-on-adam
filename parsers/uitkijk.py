"""De Uitkijk parser. Input: JSON from https://api.uitkijk.nl/z-tickets/ladder?offset=N&limit=7
(the endpoint the site's agenda loads; 7 days per page, follow offset=0,7,14,... until 'shows' is empty).
Text may be one JSON object or several concatenated (one per page); all are merged."""
import datetime, json, subprocess, time

API = "https://api.uitkijk.nl/z-tickets/ladder?offset=%d&limit=7"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

def fetch(path, max_pages=12):
    """Polite paging (1 request/second) of the ladder API; writes the pages concatenated to path. Returns pages with shows."""
    n = 0
    with open(path, "w") as f:
        for p in range(max_pages):
            r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, API % (p * 7)], capture_output=True, text=True)
            try: j = json.loads(r.stdout)
            except ValueError: break
            if not j.get("shows"): break
            f.write(r.stdout + "\n"); n += 1; time.sleep(1.0)
    return n

def _objs(text):
    dec = json.JSONDecoder(); i = 0; n = len(text)
    while i < n:
        while i < n and text[i].isspace(): i += 1
        if i >= n: break
        try: o, i = dec.raw_decode(text, i)
        except ValueError: break
        yield o

def parse(text, today):
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for o in _objs(text):
        for o2 in (o if isinstance(o, list) else [o]):
            if not isinstance(o2, dict): continue
            for day in o2.get("shows") or []:
                for sh in day.get("shows") or []:
                    title = (sh.get("title") or "").strip()
                    ds = day.get("date") or (sh.get("start_date") or "")[:10]
                    if not title or not ds: continue
                    try: d = datetime.date.fromisoformat(ds[:10])
                    except ValueError: continue
                    if d < today or d > end: continue
                    h = (sh.get("start_time") or "")[:5]
                    k = (sh.get("id"), title, ds, h)
                    if k in seen: continue
                    seen.add(k)
                    e = {"t": title, "d": d.isoformat(), "v": "De Uitkijk", "c": "film", "s": "uitkijk",
                         "u": "https://www.uitkijk.nl/film/" + sh["slug"] if sh.get("slug") else "https://www.uitkijk.nl/agenda"}
                    if h: e["h"] = h
                    out.append(e)
    return out
