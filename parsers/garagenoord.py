"""Parser for garagenoord.com/club/... (markdown dump of the "up next" list)."""
import re
import datetime

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

EVENT_RE = re.compile(
    r"\[(?P<day>\d{1,2})\]\([^)]+\)\n\n"
    r"\[(?P<mon>[A-Za-z]+),\s*(?P<year>\d{4})\]\([^)]+\)\n\n"
    r"\[Tickets\]\([^)]+\)\n\n"
    r"\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)"
)

# e.g. "Saturday, 26 September & Sunday, 27 September."
RANGE_HINT_RE = re.compile(
    r"(?P<d1>\d{1,2})\s+(?P<m1>[A-Za-z]+)\s*&\s*\w+day,?\s*(?P<d2>\d{1,2})\s+(?P<m2>[A-Za-z]+)"
)


def _resolve_year(month: int, day: int, today: datetime.date) -> int:
    year = today.year
    try:
        candidate = datetime.date(year, month, day)
    except ValueError:
        return year
    if (candidate - today).days < -60:
        return year + 1
    return year


def parse(text: str, today: datetime.date) -> list[dict]:
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else "https://www.garagenoord.com/"

    # find any "start-day month & end-day month" range hints in the page text
    range_hints = {}
    for rm in RANGE_HINT_RE.finditer(text):
        m1 = MONTHS.get(rm.group("m1").lower())
        m2 = MONTHS.get(rm.group("m2").lower())
        if not m1 or not m2:
            continue
        range_hints[(int(rm.group("d1")), m1)] = (int(rm.group("d2")), m2)

    seen = set()
    events: list[dict] = []
    window_start = today
    window_end = today + datetime.timedelta(days=120)

    for m in EVENT_RE.finditer(text):
        mon = MONTHS.get(m.group("mon").lower())
        if not mon:
            continue
        try:
            day = int(m.group("day"))
        except ValueError:
            continue
        year = int(m.group("year"))
        try:
            d = datetime.date(year, mon, day)
        except ValueError:
            continue

        title = re.sub(r"\s+", " ", m.group("title")).strip()
        title = re.sub(r"\]$", "", title)
        url = m.group("url").strip()

        key = (d.isoformat(), title, url)
        if key in seen:
            continue
        seen.add(key)

        if d < window_start or d > window_end:
            continue

        ev = {
            "t": title,
            "d": d.isoformat(),
            "v": "Garage Noord",
            "u": url,
            "c": "club",
            "s": "garagenoord",
        }

        hint = range_hints.get((day, mon))
        if hint:
            d2, m2 = hint
            y2 = year if m2 >= mon else year + 1
            try:
                ed = datetime.date(y2, m2, d2)
                if ed > d:
                    ev["ed"] = ed.isoformat()
            except ValueError:
                pass

        events.append(ev)

    return events
