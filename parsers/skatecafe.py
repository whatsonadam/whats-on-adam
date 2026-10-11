"""Parser for skatecafe.weticket.io/ (markdown dump)."""
import re
import datetime

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

EVENT_RE = re.compile(
    r"\[\w+,\s*(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2}),\s*(?P<time>\d{1,2}:\d{2})"
    r"\s*\n\n#{4,5}\s*(?P<soldout>\[SOLD OUT\]\s*)?(?P<title>.+?)\s*\n\n"
    r"(?:(?P<venue>[^\n\[\]]+)\s*\n\n)?\[Details\]\((?P<slug>[^)]+)\)"
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


def _category(title: str) -> str:
    t = title.lower()
    if "kids" in t or "skateles" in t:
        return "kids"
    if "brainwash" in t or "curious minds" in t:
        return "talk"
    if "(live)" in t and "b2b" not in t and t.count(",") <= 3:
        return "music"
    return "club"


def parse(text: str, today: datetime.date) -> list[dict]:
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else "https://skatecafe.weticket.io/"
    base = "https://skatecafe.weticket.io/"

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
        year = _resolve_year(mon, day, today)
        try:
            d = datetime.date(year, mon, day)
        except ValueError:
            continue
        if d < window_start or d > window_end:
            continue

        title = re.sub(r"\s+", " ", m.group("title")).strip()
        title = re.sub(r"\]$", "", title)
        venue = (m.group("venue") or "Skatecafe Karin & Yvonne").strip()
        slug = m.group("slug").strip()
        url = base + slug if not slug.startswith("http") else slug

        ev = {
            "t": title,
            "d": d.isoformat(),
            "h": m.group("time"),
            "v": venue,
            "u": url,
            "c": _category(title),
            "s": "skatecafe",
        }
        if m.group("soldout"):
            ev["p"] = "Sold out"
        events.append(ev)

    return events
