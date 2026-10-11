"""Parser for MEZRAB full program (mezrab.nl/full-program/)."""
import re
import datetime

ROW_RE = re.compile(
    r'\|\s*\w{3}\s+(\d{1,2})\.(\d{1,2})\s*\|\s*(\d{2}):(\d{2})\s*\|\s*'
    r'\[(.+?)\]\((https://mezrab\.nl/events/[^)]+)\)\s*\|'
)


def _classify(title: str) -> str:
    low = title.lower()
    if "♫" in title:
        return "music"
    if "comedy" in low:
        return "comedy"
    if "balfolk" in low or "dance" in low:
        return "dance"
    return "theatre"


def parse(text: str, today: datetime.date) -> list[dict]:
    window_end = today + datetime.timedelta(days=120)
    events = []

    for m in ROW_RE.finditer(text):
        dd, mm, hh, mi, title, url = m.groups()
        try:
            day = int(dd)
            month = int(mm)
        except ValueError:
            continue

        year = today.year
        if month < today.month - 2:
            year += 1
        try:
            date = datetime.date(year, month, day)
        except ValueError:
            continue

        if not (today <= date <= window_end):
            continue

        title = title.strip()
        events.append({
            "t": title,
            "d": date.isoformat(),
            "h": f"{hh}:{mi}",
            "v": "Mezrab",
            "u": url.strip(),
            "c": _classify(title),
            "s": "mezrab",
        })

    return events
