"""Parser for Parallel (parallel.am, markdown dump): the club next to Paradiso Noord at the Tolhuistuin.

The full list is in the month sections, each night rendered as ':   [DD.MM word word word](url)'. The listing has
no start times and no prices (ticket shop is my.parallel.am), so none are shown.
"""
import re
from datetime import timedelta

try:
    from _dates import make_date
except ImportError:  # pragma: no cover
    from parsers._dates import make_date

ITEM = re.compile(r":\s+\[(\d{1,2})\.(\d{1,2})\s+(.*?)\]\((https://parallel\.am/programme/[^)]+)\)", re.S)


def parse(text, today):
    out, seen = [], set()
    for m in ITEM.finditer(text):
        day, mon, raw, url = m.groups()
        d = make_date(int(day), int(mon), None, today)
        if not d or d < today or d > today + timedelta(days=240):
            continue
        title = re.sub(r"\s+", " ", raw).strip()
        sold = bool(re.search(r"sold\s*out", title, re.I))
        title = re.sub(r"\s*sold\s*out\s*$", "", title, flags=re.I).strip()
        if (d, url) in seen:
            continue
        seen.add((d, url))
        e = {"t": title, "d": d.isoformat(), "v": "Parallel", "c": "club", "u": url, "s": "parallel"}
        if sold:
            e["b"] = "Sold out"
        out.append(e)
    return out
