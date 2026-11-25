"""Activisme Agenda (activismeagenda.nl): national calendar of demonstrations and activist events.

The site runs The Events Calendar for WordPress and serves its events through the public REST API
(/wp-json/tribe/events/v1/events), so no scraping of pages is needed. The list is national; this parser keeps entries
that name Amsterdam in the title or description. The venue field is always empty on this site, the place sits in the
description. Dutch text is marked tl=1 for translation. Weekly entries (Vlaggen voor Palestina) come as one event per
date. Entries that are not demonstrations (talks, dinners) are reclassified in build.py like the other protest agendas.
"""
import datetime, html, json, re, subprocess, time

API = "https://activismeagenda.nl/wp-json/tribe/events/v1/events?per_page=50&start_date={start}&page={page}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 40
AMS = re.compile(r"\bamsterdam\b", re.I)
ONLINE = re.compile(r"\bonline\b|\bzoom\b", re.I)


def fetch(out, today=None):
    today = today or datetime.date.today()
    items = []
    for p in range(1, MAX_PAGES + 1):
        d = None
        for attempt in range(4):                    # the server resets some connections: retry a page before giving up
            r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, API.format(start=today.isoformat(), page=p)],
                               capture_output=True, text=True)
            try: d = json.loads(r.stdout); break
            except Exception: time.sleep(2 * (attempt + 1))
        if d is None:
            if items: break                         # keep what we have; a short list is better than none
            raise RuntimeError("no response")
        ev = d.get("events") or []
        if not ev: break
        items += ev
        if not d.get("next_rest_url"): break
    if not items: raise RuntimeError("no events")
    with open(out, "w") as f: json.dump(items, f)
    return len(items)


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(text, today):
    out, seen = [], set()
    for it in json.loads(text):
        title = _text(it.get("title"))
        desc = _text(it.get("description"))
        if not title or not AMS.search(title + " " + desc[:300]): continue
        if ONLINE.search(title): continue
        start = (it.get("start_date") or "")
        try: d = datetime.date.fromisoformat(start[:10])
        except ValueError: continue
        if d < today or it.get("id") in seen: continue
        seen.add(it.get("id"))
        seg = None                                  # "Title | Place, Amsterdam" or "Title – Place, Amsterdam": the tail is the place
        m = re.match(r"^(.*?)\s+[|–-]\s+([^|–]*amsterdam[^|–]*)$", title, re.I)
        if m: title, seg = m.group(1).strip(), m.group(2).strip()
        e = {"t": title, "d": d.isoformat(), "u": it.get("url"), "c": "protest", "s": "activismeagenda", "tl": 1}
        if not it.get("all_day"):
            e["h"] = start[11:16]
            end = (it.get("end_date") or "")
            if end[:10] == start[:10] and end[11:16] not in ("23:59", e["h"]): e["eh"] = end[11:16]
        # place: first bold line of the description, e.g. "Spuiplein (het Lieverdje), Amsterdam NL"
        m = re.search(r"<strong>(.*?)</strong>", it.get("description") or "", re.S)
        place = _text(m.group(1)) if m else ""
        clean = lambda x: re.sub(r"\s*,\s*Amsterdam\b.*$|,\s*NL$|\s+NL$", "", (x or "").strip(" *"), flags=re.I).strip(" ,*")
        v = clean(place)
        if not v or re.match(r"^amsterdam\b", v, re.I): v = clean(seg) or v
        v = re.sub(r"^vlaggen voor palestina\s+", "", v, flags=re.I)
        e["v"] = v[:80] if v and not re.match(r"^amsterdam", v, re.I) else "Amsterdam"
        if re.match(r"^vlaggen voor palestina\b", title, re.I): e["t"] = "Vlaggen voor Palestina"   # the address is glued to the title
        elif clean(title).lower() in ("", clean(place).lower()) or re.match(r"^(station|stadhuis)\b", title, re.I):
            e["t"] = "Demonstration at " + re.sub(r"\*$", "", title).strip()   # the organiser gave only the place as the title
            e["b"] = "The organiser gives no further details."
        rest = desc.replace(_text(m.group(1)), "", 1).strip() if m else desc
        if rest and len(rest) > 25 and not AMS.fullmatch(rest) and "b" not in e: e["b"] = rest[:200]
        out.append(e)
    return out
