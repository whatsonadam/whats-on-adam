"""Parser for amsterdamalternative.nl/agenda."""
import re
import datetime

BASE_URL = "https://www.amsterdamalternative.nl"

DAY_HEADER_RE = re.compile(
    r'^\w+ (\d{1,2}) (January|February|March|April|May|June|July|August|'
    r'September|October|November|December)(?:\s*\((\d{4})\))?\s*$'
)

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

ENTRY_RE = re.compile(
    r'\[\*\*(.+?)\*\* // (\d{2}:\d{2}) // €\s?([^\n]*)\n\n'
    r'## ((?:(?!\n\n\[\*\*).)*?)\]\((/agenda/\d+/[^)]+)\)',
    re.DOTALL,
)

VENUE_DEFAULT_CATEGORY = {
    "ot301-café gilde": "food",
    "admnoord - ‘t groene veld": "food",
    "filmhuis cavia": "film",
    "ot301-ventilator cinema": "film",
    "plein theater": "theatre",
    "badhuistheater": "theatre",
    "zid theater": "theatre",
    "mediamatic biotoop": "exhibition",
}

TITLE_CATEGORY_RULES = [
    (("workshop", "class", "cursus", "training"), "workshop"),
    (("dinner", "lunch", "eetcafe", "eetcafé", "food", "vegan", "borrel"), "food"),
    (("club", "rave", "party", " dj ", "dj "), "club"),
    (("talk", "lecture", "discussion", "q&a", "panel"), "talk"),
    (("comedy", "cabaret", "stand-up", "standup"), "comedy"),
    (("dance",), "dance"),
    (("exhibition", "expo"), "exhibition"),
    (("film", "cinema", "documentary", "movie", "screening"), "film"),
    (("kids", "children", "family"), "kids"),
    (("market",), "other"),
    (("demonstration", "riot", "protest"), "community"),
]


def _year_for(month: int, today: datetime.date) -> int:
    if month < today.month - 2:
        return today.year + 1
    return today.year


def _clean_price(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    low = raw.lower()
    if raw == "0" or low in ("free", "gratis"):
        return "Free"
    if "donation" in low:
        return "donation"
    if "uitverkocht" in low or "sold out" in low:
        return "Sold out"
    if raw.startswith("€"):
        return raw
    # "15/8" -> "€15/8" ; "17,50" -> "€17,50" ; "10 donation" -> "€10 donation"
    return "€" + raw


def _classify(title: str, venue: str) -> str:
    low_title = title.lower()
    for keywords, cat in TITLE_CATEGORY_RULES:
        if any(k in low_title for k in keywords):
            return cat
    return VENUE_DEFAULT_CATEGORY.get(venue.lower(), "music")


def parse(text: str, today: datetime.date) -> list[dict]:
    window_end = today + datetime.timedelta(days=120)
    lines = text.split("\n")

    # Map each character offset to the date it belongs under, by scanning
    # for day-header lines and recording their positions in the text.
    day_positions = []  # list of (char_offset, date)
    offset = 0
    for line in lines:
        m = DAY_HEADER_RE.match(line.strip())
        if m:
            day_s, mon_s, year_s = m.groups()
            mon = MONTH_MAP.get(mon_s.lower())
            if mon is not None:
                year = int(year_s) if year_s else _year_for(mon, today)
                try:
                    date = datetime.date(year, mon, int(day_s))
                    day_positions.append((offset, date))
                except ValueError:
                    pass
        offset += len(line) + 1  # +1 for the '\n' stripped by split

    if not day_positions:
        return []

    events = []
    for m in ENTRY_RE.finditer(text):
        pos = m.start()
        # Find the most recent day header before this entry.
        date = None
        for off, d in day_positions:
            if off <= pos:
                date = d
            else:
                break
        if date is None:
            continue
        if not (today <= date <= window_end):
            continue

        venue, time_s, price_raw, raw_body, path = m.groups()
        venue = venue.strip()
        title = raw_body.split("\n\n")[0].strip()
        title = re.sub(r'\s*Tickets\s*$', '', title).strip()
        if not title:
            continue

        events.append({
            "t": title,
            "d": date.isoformat(),
            "h": time_s.strip(),
            "v": venue,
            "u": BASE_URL + path,
            "c": _classify(title, venue),
            "p": _clean_price(price_raw),
            "s": "amsterdamalternative",
        })

    # Drop the optional price key when None to match spec (optional field).
    for e in events:
        if e.get("p") is None:
            e.pop("p", None)

    return events
