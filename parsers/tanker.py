"""Parser for De Roze Tanker (detanker.nl/agenda, markdown dump).

Each item is '[EXPO]  date line  [time]  ### Title  blurb'. Date lines look like 'vr 16 okt' or, for exhibitions,
'vr 19 jun – do 6 aug'. Items without a time are exhibitions or all-day. The agenda lists upcoming items only.
"""
import re
from datetime import timedelta

try:
    from _dates import find_dates, span, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates, span, hhmm

URL = "https://www.detanker.nl/agenda"
DATE = re.compile(r"^(?:ma|di|wo|do|vr|za|zo)\s+\d{1,2}\s+[a-z]{3,9}", re.I)
TIME = re.compile(r"^\d{1,2}:\d{2}$")
CAT = [(r"expo|opening", "exhibition"), (r"concert|jam|strings|night|gathering|release|festival|kings|noise|gospel|koor|audio|music|muziek|dj",
        "music"), (r"taalcaf|zine|workshop|kamp|maak", "workshop"), (r"literair|lezing|talk|boek", "talk")]


def _cat(title, blurb):
    t = (title + " " + blurb).lower()
    if re.search(r"taalcaf", t):
        return "community"
    for rx, c in CAT:
        if re.search(rx, t):
            return c
    return "other"


def parse(text, today):
    lines = [l.strip() for l in text.splitlines()]
    out, seen = [], set()
    for i, l in enumerate(lines):
        if not l.startswith("### ") or l[4:].strip().rstrip(":").upper() in ("DEZE WEEK", "AGENDA"):
            continue
        title = l[4:].strip()
        prev = [x for x in lines[max(0, i - 6):i] if x][-3:]
        tm = prev[-1] if prev and TIME.match(prev[-1]) else None
        dl = next((x for x in reversed(prev) if DATE.match(x)), None)
        if not dl:
            continue
        blurb = next((x for x in lines[i + 1:i + 5] if x and not x.startswith("###")), "")
        if DATE.match(blurb) or TIME.match(blurb):
            blurb = ""
        ds = find_dates(dl, today)
        if not ds:
            continue
        if len(title) > 90:
            title = title[:87].rstrip() + "…"
        cat = _cat(title, blurb)
        base = {"t": title, "c": cat, "v": "De Roze Tanker", "u": URL, "s": "tanker", "addr": "Leeuwarderweg 76"}
        if len(ds) >= 2:
            if ds[0] > today + timedelta(days=240) or ds[-1] < ds[0]:
                continue   # a range without a year that has already finished
            sp = span(ds[0], ds[-1], today)
            if not sp or (title, sp[0]) in seen:
                continue
            seen.add((title, sp[0]))
            e = dict(base, d=sp[0].isoformat(), c="exhibition")
            if sp[1]:
                e["ed"] = sp[1].isoformat()
            out.append(e)
            continue
        d = ds[0]
        if d < today or d > today + timedelta(days=240) or (title, d) in seen:
            continue
        seen.add((title, d))
        e = dict(base, d=d.isoformat(), c="other" if cat == "exhibition" else cat)
        if tm:
            e["h"] = hhmm(tm)
        if blurb:
            e["b"] = blurb[:160]
        out.append(e)
    return out
