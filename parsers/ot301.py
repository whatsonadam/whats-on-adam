"""Parser for ot301.nl/agenda (markdown dump)."""
import re
import datetime

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

DAY_HEADER_RE = re.compile(
    r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
    r"(\d{1,2})\s+([A-Za-z]+)\s*$",
    re.MULTILINE,
)

# One bracketed event entry, may be preceded by "Buy tickets" inside the brackets.
EVENT_RE = re.compile(
    r"\[(?:Buy tickets)?\*\*(?P<venue>[^*]+)\*\*\s*//\s*(?P<time>\d{1,2}:\d{2})\s*//\s*"
    r"(?P<price>[^*\[\]]+?)\*\*(?P<title>[^*]+)\*\*(?P<artists>[^\]]*)\]\((?P<url>[^)]+)\)"
)


def _resolve_year(month: int, day: int, today: datetime.date) -> int:
    year = today.year
    candidate = datetime.date(year, month, day)
    delta_days = (candidate - today).days
    if delta_days < -60:
        candidate = datetime.date(year + 1, month, day)
    return candidate.year


def _clean_price(price: str) -> str:
    price = price.strip()
    price = re.sub(r"€\s+", "€", price)
    price = re.sub(r"\s*//\s*", ", ", price)
    price = re.sub(r"\s+", " ", price).strip()
    return price


def _category(venue: str, title: str) -> str:
    t = title.lower()
    v = venue.lower()
    if "lunch" in t or "dinner" in t:
        return "food"
    if "life drawing" in t:
        return "workshop"
    if "bookbinding" in t or "intensive" in t or "workshop" in t:
        return "workshop"
    if "cinema" in v or "film" in t or "screening" in t or "premiere" in t:
        return "film"
    if "theatre" in t or "theater" in t or "improvisatie" in t:
        return "theatre"
    if "astrology" in t or "talk" in t or "asserting" in t or "right to say" in t:
        return "talk"
    if "residency" in t or "share their work" in t:
        return "exhibition"
    if v == "studios":
        return "club"
    if "gallery" in v:
        return "exhibition"
    return "other"


def parse(text: str, today: datetime.date) -> list[dict]:
    src_match = re.search(r"^SOURCE:\s*(\S+)", text, re.MULTILINE)
    source_url = src_match.group(1) if src_match else "https://ot301.nl/agenda"
    base = "https://ot301.nl"

    headers = list(DAY_HEADER_RE.finditer(text))
    if not headers:
        return []

    events: list[dict] = []
    window_start = today
    window_end = today + datetime.timedelta(days=120)

    for idx, hm in enumerate(headers):
        block_start = hm.end()
        block_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        month_name = hm.group(2).lower()
        month = MONTHS.get(month_name)
        if not month:
            continue
        try:
            day = int(hm.group(1))
        except ValueError:
            continue
        try:
            year = _resolve_year(month, day, today)
            d = datetime.date(year, month, day)
        except ValueError:
            continue

        if d < window_start or d > window_end:
            continue

        for em in EVENT_RE.finditer(block):
            venue = em.group("venue").strip()
            time_s = em.group("time").strip()
            price = _clean_price(em.group("price"))
            title = re.sub(r"\s+", " ", em.group("title")).strip()
            title = re.sub(r"\]$", "", title)
            artists = em.group("artists").strip()
            url = em.group("url").strip()
            if url.startswith("/"):
                url = base + url
            elif not url.startswith("http"):
                url = source_url

            ev = {
                "t": title,
                "d": d.isoformat(),
                "h": time_s,
                "v": venue,
                "u": url,
                "c": _category(venue, title),
                "s": "ot301",
            }
            if price:
                ev["p"] = price
            if artists:
                ev["b"] = artists[:120]
            events.append(ev)

    return events
