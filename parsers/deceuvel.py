"""Parser for deceuvel.nl/en/events/ (markdown dump)."""
import re
import datetime

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

MONTH_HEADER_RE = re.compile(r"^### (?P<mon>[A-Z][a-z]+)\s*$", re.MULTILINE)

BLOCK_RE = re.compile(
    r"\[### \w{2}\s+(?P<day>\d{1,2})\n\n"
    r"#### (?P<h>\d{1,2}:\d{2})\s*-\s*(?P<eh>\d{1,2}:\d{2})\n\n"
    r"##### Location:\n\n(?P<loc>[^\n]+)\n\n"
    r"##### Entry:\n\n(?P<entry>[^\n]+)\n\n"
    r"### (?P<title>[^\n]+?)"
    r"(?:\n\n(?P<blurb>[^\]]+?))?\]\((?P<url>[^)]+)\)"
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


def _clean_price(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", s)
    return s


def _clean_loc(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(".")
    return s


def _normalize_quotes(s: str) -> str:
    return (
        s.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def _dedupe_prefix(s: str) -> str:
    m = re.match(r"^(.{5,50}?)\s+\1\b", s)
    if m:
        return m.group(1) + s[m.end():]
    return s


def _truncate(s: str, limit: int = 120) -> str:
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


def _category(title: str) -> str:
    t = title.lower()
    if "yoga" in t or "workshop" in t or "bike kitchen" in t or "meditation" in t or "gathering" in t:
        return "workshop"
    if "choir" in t or "rehearsal" in t:
        return "music"
    if "dans" in t or "dance" in t:
        return "dance"
    if "safari" in t or "greenhouse" in t:
        return "other"
    if "market" in t or "celebration" in t or "purifying park" in t or "park afternoon" in t:
        return "community"
    return "other"


def parse(text: str, today: datetime.date) -> list[dict]:
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else "https://deceuvel.nl/en/events/"

    month_headers = list(MONTH_HEADER_RE.finditer(text))
    if not month_headers:
        return []

    events: list[dict] = []
    window_start = today
    window_end = today + datetime.timedelta(days=120)

    for bm in BLOCK_RE.finditer(text):
        # find the month in effect at this block's position
        month = None
        for mh in month_headers:
            if mh.start() <= bm.start():
                month = MONTHS.get(mh.group("mon").lower())
            else:
                break
        if not month:
            continue

        try:
            day = int(bm.group("day"))
        except ValueError:
            continue
        year = _resolve_year(month, day, today)
        try:
            d = datetime.date(year, month, day)
        except ValueError:
            continue
        if d < window_start or d > window_end:
            continue

        title = re.sub(r"\s+", " ", bm.group("title")).strip()
        title = re.sub(r"\]$", "", title)
        title = _normalize_quotes(title)
        title = _dedupe_prefix(title)
        loc = _clean_loc(bm.group("loc"))
        entry = _clean_price(bm.group("entry"))
        url = bm.group("url").strip()
        blurb = bm.group("blurb")
        blurb = _normalize_quotes(re.sub(r"\s+", " ", blurb).strip()) if blurb else ""

        ev = {
            "t": title,
            "d": d.isoformat(),
            "h": bm.group("h"),
            "eh": bm.group("eh"),
            "v": loc,
            "u": url,
            "c": _category(title),
            "s": "deceuvel",
        }
        if entry:
            ev["p"] = entry
        if blurb:
            ev["b"] = _truncate(blurb)
        events.append(ev)

    return events
