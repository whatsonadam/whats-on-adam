"""Fill in missing start times by reading each event's own page, once.

Some agenda pages list only a title and a date. For events without a time, from the sources in
SOURCES below, this opens the event page, reads the start time and saves it in times.json. Later
runs reuse the saved time, so only new events cost a page visit. If a page has no time, or can't be
read, the event simply stays without one ("Time to be confirmed" on the site).

Politeness: identifies itself, one request per second, at most MAX_FETCH pages per run.
"""
import datetime, html as _html, json, os, re, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "times.json")
UA = "whatsonadam-agenda (non-commercial hobby site; github.com/whatsonadam/whats-on-adam)"
SOURCES = ("tolhuistuin", "cinetol", "iamsterdam", "odessa", "marineterrein", "amsterdammuseum", "parallel", "radion", "dehallen")
MAX_FETCH = int(os.environ.get("PAGE_TIMES_MAX", "300"))
RETRY_AFTER_DAYS = 7
HM = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
MON = {"jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}


def _lines(page):
    t = re.sub(r"<(script|style|noscript)\b.*?</\1>", "", page, flags=re.S | re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", "\n", t))
    out = (re.sub(r"\s+", " ", l).strip() for l in t.split("\n"))
    return [l for l in out if l]


def _hm(s):
    m = HM.search(s or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def _labelled(lines, label):
    """Time that follows a label, on the same line ('Show 20:30') or the next one ('Time' / '20:30')."""
    rx = re.compile(rf"^{label}\b", re.I)
    for i, l in enumerate(lines):
        if rx.match(l):
            t = _hm(l) or (_hm(lines[i + 1]) if i + 1 < len(lines) else None)
            if t:
                return t
    return None


def read_tolhuistuin(page, today):
    lines = _lines(page)
    try:
        a = next(i for i, l in enumerate(lines) if l.lower() == "get tickets")
    except StopIteration:
        return None
    seg = []
    for l in lines[a + 1:a + 14]:
        if l.lower() == "entrance":
            break
        seg.append(l)
    show = _labelled(seg, r"(?:show|time)")
    doors = _labelled(seg, r"doors")
    end = _labelled(seg, r"end")
    rng = next((re.fullmatch(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", l) for l in seg if re.fullmatch(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", l)), None)
    start = show or (_hm(rng.group(1)) if rng else None) or doors
    stop = end or (_hm(rng.group(2)) if rng else None)
    return {"h": start, "eh": stop} if start else None


def read_cinetol(page, today):
    lines = _lines(page)
    show = _labelled(lines, r"show:?")
    doors = _labelled(lines, r"doors:?")
    start = show or doors
    return {"h": start} if start else None


def read_iamsterdam(page, today):
    """Dates and times sit together: 'zo 11 okt' / '19:00' / '-' / '20:30'. Returns {date: {h, eh}}."""
    lines = _lines(page)
    out = {}
    rx = re.compile(r"^(?:ma|di|wo|do|vr|za|zo) (\d{1,2}) (\w{3})$", re.I)
    for i, l in enumerate(lines):
        m = rx.match(l)
        if not m or m.group(2).lower() not in MON:
            continue
        mo, da = MON[m.group(2).lower()], int(m.group(1))
        yr = today.year + (1 if mo < today.month - 2 else 0)
        try:
            d = datetime.date(yr, mo, da)
        except ValueError:
            continue
        nxt = lines[i + 1:i + 4]
        start = _hm(nxt[0]) if nxt and re.fullmatch(r"\d{1,2}:\d{2}", nxt[0]) else None
        if not start:
            continue
        stop = _hm(nxt[2]) if len(nxt) >= 3 and nxt[1] == "-" and re.fullmatch(r"\d{1,2}:\d{2}", nxt[2]) else None
        out.setdefault(d.isoformat(), {"h": start, **({"eh": stop} if stop and stop != start else {})})
    return {"dates": out} if out else None


def read_odessa(page, today):
    """hipsy.nl event page: the event's own range comes first ('17:00 tot 22:00'); later ranges belong to other events."""
    for l in _lines(page):
        m = re.fullmatch(r"(\d{1,2}:\d{2})\s*(?:tot|to|-|\u2013)\s*(\d{1,2}:\d{2})", l)
        if m:
            return {"h": _hm(m.group(1)), "eh": _hm(m.group(2))}
    return None


# --- sources that list only a date; the start time sits on the event page -------------------------
T = r"(\d{1,2})[:.](\d{2})(?:\s*([ap]m))?"
RANGE = re.compile(rf"{T}\s*(?:-|\u2013|\u2014|tot|to|until)\s*{T}", re.I)
ONE = re.compile(rf"(?<![\d:.])(?:[01]?\d|2[0-3])[:.][0-5]\d(?!\d)(?:\s*[ap]m)?|(?<!\d)\d{{1,2}}\s*[ap]m", re.I)


def _t(h, m, ap=None):
    h, m = int(h), int(m)
    if ap:
        h = h % 12 + (12 if ap.lower() == "pm" else 0)
    return f"{h:02d}:{m:02d}" if h < 24 and m < 60 else None


def _first_time(s):
    m = re.search(T, s or "", re.I)
    return _t(*m.groups()) if m else None


def _range_in(line):
    m = RANGE.search(line)
    if not m:
        return None
    g = m.groups()
    a, b = _t(g[0], g[1], g[2]), _t(g[3], g[4], g[5])
    return {"h": a, **({"eh": b} if b and b != a else {})} if a else None


def _after_label(lines, label):
    """Line that starts with label (optionally 'Label: 20.00'), else the line after it."""
    rx = re.compile(rf"^{label}\b", re.I)
    for i, l in enumerate(lines):
        if rx.match(l) and len(l) < 40:
            for cand in (l, lines[i + 1] if i + 1 < len(lines) else ""):
                got = _range_in(cand) or ({"h": _first_time(cand)} if _first_time(cand) else None)
                if got and got.get("h"):
                    return got
    return None


def read_marineterrein(page, today):
    return _after_label(_lines(page), r"(?:tijden?|time|when)")


def read_amsterdammuseum(page, today):
    return _after_label(_lines(page), r"(?:time|tijd)")


def read_parallel(page, today):
    """Range on the 'AT PARALLEL' line, else a lone time right under the date line. 23:59 is a placeholder there."""
    lines = _lines(page)
    for l in lines:
        if re.search(r"\bAT PARALLEL\b", l) or re.fullmatch(r"\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}", l):
            got = _range_in(l)
            if got and got["h"] != "23:59":
                return got
    for i, l in enumerate(lines):
        if re.fullmatch(r"(?:mon|tue|wed|thu|fri|sat|sun) \d{1,2}\.\d{1,2}", l, re.I):
            for c in lines[i + 1:i + 8]:
                if re.fullmatch(r"\d{1,2}:\d{2}", c):
                    return {"h": _hm(c)} if _hm(c) != "23:59" else None
    return None


def read_radion(page, today):
    lines = _lines(page)
    start = _after_label(lines, r"doors(?: open)?")
    if not start:
        return None
    end = _after_label(lines, r"event end")
    return {"h": start["h"], **({"eh": end["h"]} if end and end["h"] != start["h"] else {})}


def read_dehallen(page, today):
    for l in _lines(page):
        if len(l) < 90 and re.search(r"\d{1,2}[:.]\d{2}", l):
            got = _range_in(l)
            if got:
                return got
    return None


READERS = {"tolhuistuin": read_tolhuistuin, "cinetol": read_cinetol, "iamsterdam": read_iamsterdam, "odessa": read_odessa,
           "marineterrein": read_marineterrein, "amsterdammuseum": read_amsterdammuseum, "parallel": read_parallel,
           "radion": read_radion, "dehallen": read_dehallen}


def _fetch(url):
    r = subprocess.run(["curl", "-sS", "-L", "-m", "25", "-A", UA, "-w", "\n%{http_code}", url], capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("\n")
    return body if code.strip() == "200" else None


def _load():
    try:
        return json.load(open(CACHE))
    except Exception:
        return {}


def _fresh_miss(ent, today):
    try:
        return (today - datetime.date.fromisoformat(ent["chk"])).days < RETRY_AFTER_DAYS
    except Exception:
        return False


def _apply(e, ent):
    got = ent.get("dates", {}).get(e["d"]) if "dates" in ent else ent
    if got and got.get("h"):
        e["h"] = got["h"]
        if got.get("eh") and got["eh"] != got["h"]:
            e["eh"] = got["eh"]
        return True
    return False


def enrich(per, today):
    """per: {source key: [events]}. Adds 'h' (and 'eh') in place where the event page has a time."""
    cache = _load()
    todo, applied = [], 0
    for key in SOURCES:
        for e in per.get(key, []):
            if e.get("h") or e.get("ed") or not e.get("u"):
                continue
            ent = cache.get(e["u"])
            if ent is None or ("none" in ent and not _fresh_miss(ent, today)):
                if e["u"] not in todo:
                    todo.append(e["u"])
    fetched = failed = 0
    by_url = {e["u"]: key for key in SOURCES for e in per.get(key, []) if e.get("u")}
    for url in todo[:MAX_FETCH]:
        key = by_url[url]
        try:
            page = _fetch(url)
            time.sleep(1.0)
            got = READERS[key](page, today) if page else None
        except Exception:
            got = None
        cache[url] = {**got, "chk": today.isoformat()} if got else {"none": True, "chk": today.isoformat()}
        fetched += 1
        failed += 0 if got else 1
    for key in SOURCES:
        for e in per.get(key, []):
            if e.get("h") or e.get("ed") or not e.get("u"):
                continue
            ent = cache.get(e["u"])
            if ent and "none" not in ent and _apply(e, ent):
                applied += 1
    # forget pages that no current event points to (after 60 days), so the file stays small
    live = {e["u"] for key in SOURCES for e in per.get(key, []) if e.get("u")}
    def _recent(v):
        try: return (today - datetime.date.fromisoformat(v["chk"])).days <= 60
        except Exception: return False
    cache = {u: v for u, v in cache.items() if u in live or _recent(v)}
    json.dump(dict(sorted(cache.items())), open(CACHE, "w"), ensure_ascii=False, indent=0)
    print(f"start times: {applied} filled from event pages ({fetched} pages read this run, {failed} without a time, {max(0, len(todo) - MAX_FETCH)} waiting for the next run)")
    return applied
