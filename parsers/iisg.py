"""Parser for the International Institute of Social History (iisg.amsterdam/nl/events, markdown dump).

Items look like '## [Title](/nl/events/slug)' followed by 'D maand YYYY HH:MM - D maand YYYY HH:MM'.
Exhibitions (title starts with 'Tentoonstelling') run from today until the end date; the rest are talks.
"""
import re
from datetime import timedelta

try:
    from _dates import MONTHS, make_date, span
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date, span

BASE = "https://iisg.amsterdam"
STAMP = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(20\d\d)\s+(\d{1,2}:\d{2})", re.I)


def parse(text, today):
    out = []
    for m in re.finditer(r"^##\s*\[([^\]]+)\]\((/[^)]+)\)\s*\n+([^\n]+)", text, re.M):
        title, path, when = m.groups()
        st = STAMP.findall(when)
        if not st:
            continue
        (d1, m1, y1, t1), (d2, m2, y2, t2) = st[0], st[-1]
        start = make_date(int(d1), MONTHS.get(m1.lower(), 0), y1, today)
        end = make_date(int(d2), MONTHS.get(m2.lower(), 0), y2, today)
        if not start or not end:
            continue
        url = BASE + path
        if re.match(r"tentoonstelling", title, re.I):
            sp = span(start, end, today)
            if not sp:
                continue
            e = {"t": re.sub(r"^Tentoonstelling:\s*", "", title), "d": sp[0].isoformat(), "c": "exhibition"}
            if sp[1]:
                e["ed"] = sp[1].isoformat()
        else:
            if end < today or start > today + timedelta(days=240):
                continue
            e = {"t": title, "d": start.isoformat(), "h": t1, "c": "talk"}
            if end == start and t2 != t1:
                e["eh"] = t2
            elif end > start:
                e["ed"] = end.isoformat()
        e.update({"v": "IISG", "u": url, "s": "iisg"})
        out.append(e)
    return out
