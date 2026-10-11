"""Parser for LAB111 cinema programme (lab111.nl/programma)."""
import re
import datetime

MONTH_MAP = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

TITLE_RE = re.compile(r'^## \[(.+?)\]\((https://www\.lab111\.nl/movie/[^)]+)\)')
ROW_RE = re.compile(
    r'^\| \[\w\w (\d\d?) (\w\w\w) (\d\d):(\d\d)\]\((https://tickets\.lab111\.nl[^)]+)\) \| ([^|]+?) \| '
)


def _year_for(month: int, today: datetime.date) -> int:
    if month < today.month - 2:
        return today.year + 1
    return today.year


def parse(text: str, today: datetime.date) -> list[dict]:
    window_end = today + datetime.timedelta(days=120)
    lines = text.split("\n")
    events = []
    seen = set()
    current_title = None
    current_url = None

    for line in lines:
        m = TITLE_RE.match(line)
        if m:
            current_title = m.group(1).strip()
            current_url = m.group(2).strip()
            continue
        m2 = ROW_RE.match(line)
        if m2 and current_title is not None:
            day_s, mon_abbr, hh, mm, ticket_url, _screen = m2.groups()
            month = MONTH_MAP.get(mon_abbr.lower())
            if month is None:
                continue
            try:
                day = int(day_s)
            except ValueError:
                continue
            year = _year_for(month, today)
            try:
                date = datetime.date(year, month, day)
            except ValueError:
                continue
            if not (today <= date <= window_end):
                continue

            key = (current_title, date.isoformat(), f"{hh}:{mm}")
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "t": current_title,
                "d": date.isoformat(),
                "h": f"{hh}:{mm}",
                "v": "LAB111",
                "u": ticket_url.strip(),
                "c": "film",
                "s": "lab111",
            })

    return events
