"""Parser for ccamstel.nl/programma (markdown dump)."""
import re
import datetime

MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}

BLOCK_RE = re.compile(
    r"^\[(?P<cat>[^\n\]]+)\n\n"
    r"## (?P<title>.+?)\n\n"
    r"(?P<sub>.*?)\]\((?P<url>[^)]+)\)",
    re.MULTILINE | re.DOTALL,
)

SESSION_RE = re.compile(
    r"^(?:ma|di|wo|do|vr|za|zo)\n(?P<day>\d{2})\n(?P<mon>[a-z]{3})\n(?P<time>\d{2}:\d{2})\s*$",
    re.MULTILINE,
)

RANGE_RE = re.compile(
    r"(?P<days>\d{1,2}(?:,\s*\d{1,2})*(?:\s+en\s+\d{1,2})?)\s+(?P<mon>[a-z]+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)

MONTHS_LONG = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}


def _category(cat: str, title: str, blurb: str) -> str:
    c = cat.lower()
    t = f"{title} {blurb}".lower()
    if "lezing" in t or "talk" in t:
        return "talk"
    if "jeugd" in c:
        return "kids"
    if "dans" in c:
        return "dance"
    if "wandeling" in t:
        return "other"
    if "theater" in c or "circus" in c or "sociaal" in c or "festival" in c:
        return "theatre"
    if "muziek" in c:
        return "music"
    return "other"


def _truncate(s: str, limit: int = 120) -> str:
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;: ") + "…"


def _resolve_year(month: int, day: int, today: datetime.date) -> int:
    year = today.year
    try:
        candidate = datetime.date(year, month, day)
    except ValueError:
        return year
    if (candidate - today).days < -60:
        return year + 1
    return year


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\]$", "", title)
    return title


def parse(text: str, today: datetime.date) -> list[dict]:
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else "https://ccamstel.nl/programma"
    base = "https://ccamstel.nl"

    blocks = list(BLOCK_RE.finditer(text))
    if not blocks:
        return []

    events: list[dict] = []
    window_start = today
    window_end = today + datetime.timedelta(days=120)

    for idx, bm in enumerate(blocks):
        cat_raw = bm.group("cat").strip()
        title = _clean_title(bm.group("title"))
        url = bm.group("url").strip()
        if url.startswith("/"):
            url = base + url
        elif not url.startswith("http"):
            url = source_url

        block_start = bm.end()
        block_end = blocks[idx + 1].start() if idx + 1 < len(blocks) else len(text)
        block = text[block_start:block_end]

        sessions = list(SESSION_RE.finditer(block))

        # blurb: first non-empty paragraph after the last session (or after
        # the ticket/genre header area if there are no sessions)
        blurb = ""
        tail_start = sessions[-1].end() if sessions else 0
        tail = block[tail_start:]
        for para in tail.split("\n\n"):
            para = para.strip()
            if not para:
                continue
            if para.startswith("*") or para.startswith("["):
                continue
            blurb = re.sub(r"\s+", " ", para).strip()
            break

        if sessions:
            for sm in sessions:
                day = int(sm.group("day"))
                mon = MONTHS.get(sm.group("mon").lower())
                if not mon:
                    continue
                year = _resolve_year(mon, day, today)
                try:
                    d = datetime.date(year, mon, day)
                except ValueError:
                    continue
                if d < window_start or d > window_end:
                    continue
                ev = {
                    "t": title,
                    "d": d.isoformat(),
                    "h": sm.group("time"),
                    "v": "CC Amstel",
                    "u": url,
                    "c": _category(cat_raw, title, blurb),
                    "s": "ccamstel",
                }
                if blurb:
                    ev["b"] = _truncate(blurb)
                events.append(ev)
        else:
            # possible multi-day range description, e.g. "3, 4, 5 en 6 december 2026"
            rm = RANGE_RE.search(block[:tail_start] if tail_start else block)
            if not rm:
                rm = RANGE_RE.search(block)
            if not rm:
                continue
            days_str = rm.group("days")
            day_nums = [int(x) for x in re.findall(r"\d{1,2}", days_str)]
            if not day_nums:
                continue
            mon = MONTHS_LONG.get(rm.group("mon").lower())
            if not mon:
                continue
            year = int(rm.group("year"))
            try:
                d_start = datetime.date(year, mon, min(day_nums))
                d_end = datetime.date(year, mon, max(day_nums))
            except ValueError:
                continue
            if d_end < window_start or d_start > window_end:
                continue
            ev = {
                "t": title,
                "d": d_start.isoformat(),
                "v": "CC Amstel",
                "u": url,
                "c": _category(cat_raw, title, blurb),
                "s": "ccamstel",
            }
            if d_end != d_start:
                ev["ed"] = d_end.isoformat()
            if blurb:
                ev["b"] = _truncate(blurb)
            events.append(ev)

    return events
