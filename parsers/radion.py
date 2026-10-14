"""Parser for RADION (radion.amsterdam/program, markdown dump).

Each night is one link: [WEEKDAY / DD.MM / TITLE / teaser (/ ADE) →](url). The listing gives no start time
(doors are usually 23:00 on Fri/Sat), so none is shown.
"""
import re
from datetime import date, timedelta

try:
    from _dates import make_date
except ImportError:  # pragma: no cover
    from parsers._dates import make_date

ITEM = re.compile(
    r"\[(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s*\n+\s*(\d{1,2})\.(\d{1,2})\s*\n+\s*(.+?)\n+(.*?)→\]\((https://radion\.amsterdam/program/[^)]+)\)",
    re.S,
)


def parse(text, today):
    out, seen = [], set()
    for m in ITEM.finditer(text):
        day, mon, title, rest, url = m.groups()
        d = make_date(int(day), int(mon), None, today)
        if not d or d < today or d > today + timedelta(days=240):
            continue
        title = re.sub(r"\s+", " ", title).strip()
        if (d, title.lower()) in seen:
            continue
        seen.add((d, title.lower()))
        teaser = re.sub(r"\s+", " ", re.sub(r"\n+\s*ADE\s*$", "", rest.strip())).strip()
        e = {"t": title, "d": d.isoformat(), "v": "RADION", "c": "club", "u": url, "s": "radion"}
        if teaser:
            e["b"] = teaser[:160]
        out.append(e)
    return out
