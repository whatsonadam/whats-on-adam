"""Parser for vrankrijk.org/events/ (markdown dump of the events listing page)."""
import re
import datetime

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

EVENT_RE = re.compile(
    r"^## \[(?P<title>.+?)\]\((?P<url>[^)]+)\)\s*$",
    re.MULTILINE,
)

# Day, Mon DD | time info | extra
LINE_RE = re.compile(
    r"^(?P<dow>\w+),\s*(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s*\|\s*(?P<rest>.*?)\s*\|?\s*$"
)

TIME_RANGE_RE = re.compile(
    r"(\d{1,2})[.\s](\d{2})\s*(?:-|to|till|until)\s*(\d{1,2})[.\s](\d{2})"
)
TIME_ONE_RE = re.compile(r"(\d{1,2})[.\s](\d{2})")


def _resolve_year(month: int, day: int, today: datetime.date) -> int:
    year = today.year
    candidate = datetime.date(year, month, day)
    # if candidate is more than ~2 months in the past, assume next year
    delta_days = (candidate - today).days
    if delta_days < -60:
        candidate = datetime.date(year + 1, month, day)
    return candidate.year


def _category(title: str) -> str:
    t = title.lower()
    if "no voku" in t or "mtg" in t:
        return "community"
    if "queer" in t:
        return "club"
    if "punk" in t:
        return "music"
    if "bangs festival" in t:
        return "music"
    if "dark expressions" in t:
        return "dance"
    if "bike repair" in t:
        return "community"
    if "street medics" in t:
        return "community"
    if "aaah" in t:
        return "community"
    return "community"


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\]$", "", title)
    return title


def parse(text: str, today: datetime.date) -> list[dict]:
    events: list[dict] = []
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else ""

    lines = text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        m = EVENT_RE.match(lines[i])
        if not m:
            i += 1
            continue
        title = _clean_title(m.group("title"))
        url = m.group("url").strip()

        # find the date/time line within the next few lines
        date_line = None
        for j in range(i + 1, min(i + 5, n)):
            lm = LINE_RE.match(lines[j].strip())
            if lm:
                date_line = lm
                break
        i += 1
        if not date_line:
            continue

        mon_key = date_line.group("mon").lower()[:3]
        month = MONTHS.get(mon_key)
        if not month:
            continue
        try:
            day = int(date_line.group("day"))
        except ValueError:
            continue

        try:
            year = _resolve_year(month, day, today)
            d = datetime.date(year, month, day)
        except ValueError:
            continue

        rest = date_line.group("rest")
        # split off trailing free-text price/extra info after a second '|'
        parts = rest.split("|")
        time_part = parts[0].strip()
        extra = "|".join(parts[1:]).strip() if len(parts) > 1 else ""

        h = eh = None
        rm = TIME_RANGE_RE.search(time_part)
        if rm:
            h = f"{int(rm.group(1)):02d}:{rm.group(2)}"
            eh = f"{int(rm.group(3)):02d}:{rm.group(4)}"
        else:
            om = TIME_ONE_RE.search(time_part)
            if om:
                h = f"{int(om.group(1)):02d}:{om.group(2)}"

        price = extra if extra else None

        ev = {
            "t": title,
            "d": d.isoformat(),
            "v": "Vrankrijk",
            "u": url if url.startswith("http") else source_url,
            "c": _category(title),
            "s": "vrankrijk",
        }
        if h:
            ev["h"] = h
        if eh:
            ev["eh"] = eh
        if price:
            ev["p"] = price
        events.append(ev)

    window_start = today
    window_end = today + datetime.timedelta(days=120)
    out = []
    for ev in events:
        d = datetime.date.fromisoformat(ev["d"])
        end_d = datetime.date.fromisoformat(ev["ed"]) if "ed" in ev else d
        if end_d < window_start or d > window_end:
            continue
        out.append(ev)
    return out
