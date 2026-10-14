"""Parser for De Hallen Amsterdam (dehallen-amsterdam.nl/en/agenda, markdown dump).

Cards: '[Category / ### Title / Space / , / date text / blurb](/en/agenda/slug)'. The page repeats cards (a featured
block and the full agenda), so duplicates are dropped. Cinema (De Filmhallen has its own source) and shop pop-ups are
skipped, and so are standing programmes that run for weeks (e.g. the weekly talk-show audience).
Dates come in many styles: '14.10.2026', '16 & 17 October 2026', 'October 17', 'October 29 to November 8',
'9 oktober t/m 29 oktober', 'Sunday, November 1st', 'Vandaag'. The cards give no start times.
"""
import re
from datetime import date, timedelta

try:
    from _dates import find_dates, lead_days, span
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates, lead_days, span

BASE = "https://www.dehallen-amsterdam.nl"
CARD = re.compile(r"\[([^\n\]]+)\n\s*###\s*([^\n]+)\n\s*([^\n]+)\n\s*,\n\s*([^\n]+)\n(.*?)\]\((/en/agenda/[^)]+)\)", re.S)
SKIP_CAT = re.compile(r"^(film|shops?)$", re.I)
CAT = [
    (r"expo", "exhibition"), (r"market", "community"), (r"music", "music"), (r"workshop", "workshop"),
    (r"famil|kids", "kids"), (r"talk|lecture", "talk"),
]


def _category(raw):
    for rx, c in CAT:
        if re.search(rx, raw, re.I):
            return c
    return "other"


def _dates(dl, today):
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b", dl)
    if m:
        try:
            return [date(int(m.group(3)), int(m.group(2)), int(m.group(1)))], False
        except ValueError:
            return [], False
    if re.search(r"\b(vandaag|today)\b", dl, re.I):
        return [today], False
    lead = lead_days(dl, today)
    if lead:
        return lead, False
    ds = find_dates(dl, today)
    ranged = bool(re.search(r"\bt/m\b|\bto\b|\buntil\b|\btill\b|–", dl, re.I)) and len(ds) >= 2
    return ds, ranged


def parse(text, today):
    out, seen = [], set()
    for m in CARD.finditer(text):
        raw_cat, title, space, dl, _rest, path = m.groups()
        if SKIP_CAT.match(raw_cat.strip()):
            continue
        cat = _category(raw_cat)
        ds, ranged = _dates(dl, today)
        if not ds:
            continue
        title = title.strip()
        venue = "De Hallen" + (f" · {space.strip()}" if space.strip() and not space.strip().startswith("De Hallen") else "")
        url = BASE + path
        if ranged or (re.search(r"vanaf|from", dl, re.I) and len(ds) >= 2):
            start, end = ds[0], ds[-1]
            if cat == "exhibition":
                sp = span(start, end, today)
                if not sp or (title, sp[0]) in seen:
                    continue
                seen.add((title, sp[0]))
                e = {"t": title, "d": sp[0].isoformat(), "c": cat, "v": venue, "u": url, "s": "dehallen"}
                if sp[1]:
                    e["ed"] = sp[1].isoformat()
                out.append(e)
            elif (end - start).days <= 14 and end >= today:
                d0 = max(start, today)
                key = (title, d0)
                if key not in seen:
                    seen.add(key)
                    out.append({"t": title, "d": d0.isoformat(), "ed": end.isoformat(), "c": cat, "v": venue,
                                "u": url, "s": "dehallen"})
            continue
        for d in ds:
            if d < today or d > today + timedelta(days=240) or (title, d) in seen:
                continue
            seen.add((title, d))
            out.append({"t": title, "d": d.isoformat(), "c": "exhibition" if cat == "exhibition" else cat, "v": venue,
                        "u": url, "s": "dehallen"})
    return out
