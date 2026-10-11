"""Parser for Volkshotel agenda (txt/volkshotel.md).

The rendered page has a "Programme" bullet list of upcoming special events
(each: `* [**Day, DD Mon**\n  time - time\n\n  **price**\n\n  ## Title\n\n
venue](url)`), followed by an "## Activities" list of recurring weekly
things with no explicit dates (skipped per spec: no parseable date).
"""
import re
from datetime import date, timedelta

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

ITEM_RE = re.compile(r'\*\s*\[\*\*(.+?)\*\*\s*(.*?)\]\(([^)]+)\)', re.DOTALL)
DAY_RE = re.compile(r'(\d{1,2})\s+([A-Za-z]+)')
TIME_RE = re.compile(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2}|end)')
BOLD_RE = re.compile(r'\*\*([^*\n]+)\*\*\s*(\([^)]*\))?')
TITLE_RE = re.compile(r'##\s*(.+)')


def _month_from_str(s):
    return MONTHS.get(s.lower()[:3])


def _infer_year(month, day, today):
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=45):
            return y
    return today.year


def _guess_category(title, venue):
    low = title.lower()
    if 'dance' in low:
        return 'dance'
    if 'market' in low:
        return 'other'
    if 'jazz' in low or 'band' in low:
        return 'music'
    if venue in ('Doka', 'Canvas', 'Station Werkplaats'):
        return 'club'
    return 'other'


def parse(text: str, today: date) -> list:
    source_url = ''
    for line in text.split('\n')[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break

    # known sub-venue names, taken from the page's own nav menu (e.g. "Doka",
    # "Canvas", "Werkplaats", "Badplaats", "Volkshotel"), so a bullet's
    # trailing tag that names one of them is a real venue, not a show title.
    known_venues = set(re.findall(
        r'\*\s*\[([A-Za-z]+)\]\(https://www\.volkshotel\.nl/en/agenda/[a-z-]+/?\)', text))
    known_venues.add('Volkshotel')

    try:
        programme_start = text.index('Programme')
    except ValueError:
        programme_start = 0
    try:
        activities_start = text.index('## Activities')
    except ValueError:
        activities_start = len(text)
    section = text[programme_start:activities_start]

    events = []
    for m in ITEM_RE.finditer(section):
        day_header, body, url = m.group(1), m.group(2), m.group(3).strip()
        dm = DAY_RE.search(day_header)
        if not dm:
            continue
        day = int(dm.group(1))
        month = _month_from_str(dm.group(2))
        if not month:
            continue

        tm = TIME_RE.search(body)
        time1 = tm.group(1) if tm else None
        time2 = tm.group(2) if tm else None
        if time2 == 'end':
            time2 = None

        bm = BOLD_RE.search(body)
        price = None
        if bm:
            price = bm.group(1).strip()
            if bm.group(2):
                price = f"{price} ({bm.group(2)[1:-1].lower()})"

        tim = TITLE_RE.search(body)
        title = tim.group(1).strip() if tim else None
        if not title:
            continue

        body_lines = [l.strip() for l in body.split('\n') if l.strip()]
        venue = body_lines[-1] if body_lines else 'Volkshotel'
        venue = re.sub(r'^#+\s*', '', venue).strip()
        # when the tag is just a repeat of the event's own title (a named
        # weekly series, not a real sub-venue), fall back to the hotel name
        if not any(v.lower() in venue.lower() for v in known_venues):
            venue = 'Volkshotel'

        yr = _infer_year(month, day, today)
        try:
            d = date(yr, month, day)
        except ValueError:
            continue

        ev = {
            't': title,
            'd': d.isoformat(),
            'v': venue,
            'u': url or source_url,
            'c': _guess_category(title, venue),
            's': 'volkshotel',
        }
        if time1:
            ev['h'] = time1
        if time2:
            ev['eh'] = time2
        if price:
            ev['p'] = price
        events.append(ev)

    window_end = today + timedelta(days=120)
    return [e for e in events if today <= date.fromisoformat(e['d']) <= window_end]
