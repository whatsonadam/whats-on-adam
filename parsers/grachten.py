"""Parser for the Museum of the Canals temporary exhibitions page (grachten.museum, markdown dump).

Only exhibitions are listed (the museum's calendar page loads its events with JavaScript and comes back empty).
'Now showing' items run from today to their end date; 'Upcoming' items start on their start date.
"""
import re
from datetime import timedelta

try:
    from _dates import find_dates, span
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates, span

URL = "https://grachten.museum/en/temporary-exhibitions/"


def _section(text, name, stop):
    m = re.search(rf"##\s*{name}\s*\n(.*?)(?=##\s*{stop}|\Z)", text, re.S)
    return m.group(1) if m else ""


def _items(block):
    for m in re.finditer(r"\[[^\]]*\]\((https://grachten\.museum/[^)]+)\)\s*\n+###\s*([^\n]+)\n+([^\n]*)", block):
        yield m.group(1), m.group(2).strip(), m.group(3).strip()


def parse(text, today):
    out = []
    for name, stop, upcoming in (("Now showing", "Upcoming", False), ("Upcoming", "Past", True)):
        for url, title, desc in _items(_section(text, name, stop)):
            dates = find_dates(desc, today)
            if not dates:
                continue
            start, end = (dates[0], dates[-1]) if len(dates) > 1 else (None, dates[0])
            if upcoming and not start:
                start, end = dates[0], None
            if upcoming and start > today + timedelta(days=240):
                continue
            sp = span(start, end, today)
            if not sp:
                continue
            title = re.sub(r"^Exhibition\s+", "", title)
            e = {"t": title, "d": sp[0].isoformat(), "v": "Museum of the Canals", "c": "exhibition", "u": url,
                 "s": "grachten"}
            if sp[1]:
                e["ed"] = sp[1].isoformat()
            out.append(e)
    return out
