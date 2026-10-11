"""Parser for Odessa Amsterdam (ecstatic dance events, listed via hipsy.nl links)."""
import re
import datetime

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "mrt": 3, "apr": 4, "may": 5, "mei": 5,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "okt": 10,
    "nov": 11, "dec": 12,
}

DATE_LINK_RE = re.compile(
    r'^\[\w{3}\s+(\d{1,2})\s+([A-Za-z]+)\]\(([^)]+)\)\s*$'
)
TITLE_LINK_RE = re.compile(r'^\[(.+?)\]\((https?://[^)]+)\)\s*$')


def _year_for_month(month: int, today: datetime.date) -> int:
    # Pick the year that puts the date closest to today, going forward.
    candidate = datetime.date(today.year, month, 1)
    if candidate < datetime.date(today.year, today.month, 1) and \
            (today.month - month) % 12 > 2:
        return today.year + 1
    if month < today.month - 2:
        return today.year + 1
    return today.year


def parse(text: str, today: datetime.date) -> list[dict]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    events = []
    i = 0
    n = len(lines)
    window_end = today + datetime.timedelta(days=120)

    while i < n:
        m = DATE_LINK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        day_s, mon_s, _date_url = m.groups()
        mon = MONTHS.get(mon_s.lower())
        if mon is None:
            i += 1
            continue
        try:
            day = int(day_s)
        except ValueError:
            i += 1
            continue
        year = _year_for_month(mon, today)
        try:
            date = datetime.date(year, mon, day)
        except ValueError:
            i += 1
            continue

        # Next non-empty line should be the title link.
        title = None
        url = None
        if i + 1 < n:
            m2 = TITLE_LINK_RE.match(lines[i + 1])
            if m2:
                title = m2.group(1).strip()
                url = m2.group(2).strip()
                i += 1

        if title is None:
            i += 1
            continue

        if today <= date <= window_end:
            events.append({
                "t": title,
                "d": date.isoformat(),
                "v": "Odessa Amsterdam",
                "u": url,
                "c": "dance",
                "s": "odessa",
            })
        i += 1

    return events
