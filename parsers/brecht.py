"""Parser for Café Brecht (cafebrecht.nl/agenda, markdown dump).

Entries are separated by a line of dashes; each has a month, a day number, start and end time, a title and a
blurb. Opening-hours notices (holiday hours) are skipped.
"""
import re
from datetime import timedelta

try:
    from _dates import MONTHS, make_date, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date, hhmm

URL = "https://www.cafebrecht.nl/agenda"
NOT_AN_EVENT = re.compile(r"vakantie|geopend|open(ings)?tijd|gesloten|winterzauber", re.I)


def parse(text, today):
    out = []
    for chunk in re.split(r"\n-{10,}\n", text):
        lines = [l.strip() for l in chunk.splitlines() if l.strip() and l.strip() != "-"]
        mi = next((i for i, l in enumerate(lines) if l.lower() in MONTHS and len(l) > 3), None)
        if mi is None or mi + 3 >= len(lines):
            continue
        day = lines[mi + 1]
        if not day.isdigit():
            continue
        h = hhmm(lines[mi + 2])
        k = mi + 3
        eh = hhmm(lines[k]) if k < len(lines) else None
        k += 1 if eh else 0
        if k >= len(lines):
            continue
        title = lines[k]
        blurb = lines[k + 1] if k + 1 < len(lines) else ""
        d = make_date(int(day), MONTHS[lines[mi].lower()], None, today)
        if not d or d < today or d > today + timedelta(days=240) or NOT_AN_EVENT.search(title):
            continue
        title = re.sub(r"\s+", " ", title).strip()
        e = {"t": title, "d": d.isoformat(), "v": "Café Brecht", "c": "other", "u": URL, "s": "brecht"}
        if h:
            e["h"] = h
        if eh and eh != h and eh > (h or "00:00"):
            e["eh"] = eh
        if blurb:
            e["b"] = blurb[:160]
        out.append(e)
    return out
