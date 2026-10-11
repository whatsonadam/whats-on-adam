"""Parser for offbeat.amsterdam (alternative Amsterdam agenda aggregator)."""
import re
import datetime

BASE_URL = "https://offbeat.amsterdam"

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

ONGOING_RE = re.compile(
    r'\[([^\]]+)\]\((/event/[^)]+)\)\s*\n'
    r'Until (\w+), (\w+) (\d{1,2})(?:, (\d{4}))?\s*\n\n'
    r'\[([^\]]+)\]\(/place/'
)

DATE_LINE_RE = re.compile(
    r'^(\w+), (\w+) (\d{1,2})(?:, (\d{4}))?, '
    r'(\d{1,2}:\d{2} [AP]M)(?:-(\d{1,2}:\d{2} [AP]M))?\s*$'
)
SECOND_LINE_RE = re.compile(
    r'^\s*\w+ (\d{1,2}) (\w+) (\d{2}:\d{2})\s*$'
)
VENUE_RE = re.compile(r'\[([^\]]+)\]\(/place/')
TAG_RE = re.compile(r'\[([\w&\'-]+)\]\(/tag/')

# Priority-ordered keyword -> category. Checked against title first, then tags.
CATEGORY_RULES = [
    (("workshop", "masterclass", "cursus"), "workshop"),
    (("comedy", "cabaret", "stand-up", "standup"), "comedy"),
    (("dinner", "food", "vegan", "restaurant", "lunch", "eetcafe", "borrel"), "food"),
    (("club", "rave", "dj", "techno", "house", "all night"), "club"),
    (("film", "cinema", "documentary", "movie"), "film"),
    (("talk", "discussion", "lecture", "q&a"), "talk"),
    (("dance", "choreography", "ballet"), "dance"),
    (("theatre", "theater", "storytelling", "performance"), "theatre"),
    (("kids", "children", "family"), "kids"),
    (("exhibition", "expo", "gallery"), "exhibition"),
    (("community", "meetup", "social"), "community"),
    (("music", "concert", "live", "band", "gig", "festival", "festivals"), "music"),
]


def _classify(title: str, tags: list[str]) -> str:
    low_title = title.lower()
    low_tags = [t.lower() for t in tags]
    for keywords, cat in CATEGORY_RULES:
        if any(k in low_title for k in keywords):
            return cat
    for keywords, cat in CATEGORY_RULES:
        if any(any(k in t for k in keywords) for t in low_tags):
            return cat
    return "other"


_LEADING_EMOJI_RE = re.compile(r'^[\U0001F000-\U0001FFFF☀-➿]+\s*')


def _clean_title(title: str) -> str:
    title = title.strip()
    title = _LEADING_EMOJI_RE.sub('', title)
    title = re.sub(r'[:\s]*0000-00-00\s*$', '', title)
    return title.strip()


def _year_for(month: int, today: datetime.date) -> int:
    if month < today.month - 2:
        return today.year + 1
    return today.year


def _to_24h(t: str) -> str:
    # t like "09:00 AM" or "05:00 PM"
    dt = datetime.datetime.strptime(t, "%I:%M %p")
    return dt.strftime("%H:%M")


def parse(text: str, today: datetime.date) -> list[dict]:
    window_end = today + datetime.timedelta(days=120)
    events = []

    # --- Ongoing (exhibition-style, running through some end date) ---
    ongoing_start = text.find("## Ongoing")
    main_start = text.find("\n[## ")
    if ongoing_start != -1 and main_start != -1 and main_start > ongoing_start:
        ongoing_text = text[ongoing_start:main_start]
        for m in ONGOING_RE.finditer(ongoing_text):
            raw_title, path, _wd, mon_s, day_s, year_s, venue = m.groups()
            mon = MONTH_MAP.get(mon_s.lower()[:3])
            if mon is None:
                continue
            try:
                day = int(day_s)
            except ValueError:
                continue
            year = int(year_s) if year_s else _year_for(mon, today)
            try:
                end_date = datetime.date(year, mon, day)
            except ValueError:
                continue
            if end_date < today:
                continue  # already ended
            if today > window_end:
                continue
            title = _clean_title(raw_title)
            events.append({
                "t": title,
                "d": today.isoformat(),
                "ed": end_date.isoformat(),
                "v": venue.strip(),
                "u": BASE_URL + path,
                "c": "exhibition",
                "s": "offbeat",
            })

    # --- Main day-by-day listing ---
    if main_start == -1:
        return events

    blocks = text[main_start:].split("\n[## ")[1:]
    for block in blocks:
        m = re.match(r'(.+?)\]\((/event/[^)]+)\)\s*\n', block)
        if not m:
            continue
        raw_title = m.group(1)
        path = m.group(2)
        rest = block[m.end():]

        lines = rest.split("\n")
        # Find first non-empty line: the date line.
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines):
            continue
        dm = DATE_LINE_RE.match(lines[idx].strip())
        if not dm:
            continue
        _wd, mon_s, day_s, year_s, start_t, end_t = dm.groups()
        mon = MONTH_MAP.get(mon_s.lower()[:3])
        if mon is None:
            continue
        try:
            day = int(day_s)
        except ValueError:
            continue
        year = int(year_s) if year_s else _year_for(mon, today)
        try:
            date = datetime.date(year, mon, day)
        except ValueError:
            continue

        idx += 1
        second_line_date = None
        if idx < len(lines) and SECOND_LINE_RE.match(lines[idx]):
            sm = SECOND_LINE_RE.match(lines[idx])
            sec_day, sec_mon_s, _sec_time = sm.groups()
            sec_mon = MONTH_MAP.get(sec_mon_s.lower()[:3])
            if sec_mon is not None:
                try:
                    sec_year = year if sec_mon >= mon else _year_for(sec_mon, today)
                    second_line_date = datetime.date(sec_year, sec_mon, int(sec_day))
                except ValueError:
                    second_line_date = None
            idx += 1

        if not (today <= date <= window_end):
            # allow if it's a multi-day span overlapping the window via second date
            if not (second_line_date and today <= second_line_date <= window_end and date <= window_end):
                continue

        venue_m = VENUE_RE.search(rest)
        venue = venue_m.group(1).strip() if venue_m else ""

        tags = TAG_RE.findall(rest)
        title = _clean_title(raw_title)

        event = {
            "t": title,
            "d": date.isoformat(),
            "v": venue,
            "u": BASE_URL + path,
            "c": _classify(title, tags),
            "s": "offbeat",
            "tags": [t.lower() for t in tags],
        }

        all_day = (start_t == "12:00 AM" and end_t == "11:59 PM")
        if all_day:
            if second_line_date and second_line_date != date:
                event["ed"] = second_line_date.isoformat()
        else:
            event["h"] = _to_24h(start_t)
            if end_t:
                event["eh"] = _to_24h(end_t)

        events.append(event)

    return events
