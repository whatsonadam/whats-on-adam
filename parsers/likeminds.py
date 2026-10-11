"""Parser for Likeminds agenda (txt/likeminds.md).

Structure: a "# <Month>, <Year>" heading sets the month/year context for the
events that follow, each shaped as
`[DD\n\n[DD2\n\n]TITLE](ticket_url)\n\n[Tickets](url)\n\n[Lees meer](event_url)\n\nVenue`.
"""
import re
from datetime import date, timedelta

MONTHS = {
    'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'augustus': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'december': 12,
}

MONTH_HEADING_RE = re.compile(r'^#\s+([A-Za-z]+),\s*(\d{4})\s*$', re.MULTILINE)
EVENT_RE = re.compile(
    r'\[(\d{2})\s*\n\n(?:(\d{2})\s*\n\n)?(.+?)\]\([^)]+\)\s*\n\n'
    r'\[Tickets\]\([^)]+\)\s*\n\n'
    r'\[Lees meer\]\(([^)]+)\)\s*\n\n'
    r'([^\n]+)',
    re.DOTALL,
)


def _month_from_str(s):
    s = s.lower()
    for name, num in MONTHS.items():
        if s.startswith(name[:4]):
            return num
    return None


def _clean_title(s):
    s = re.sub(r'\s+', ' ', s).strip()
    if s.isupper() and len(s.split()) > 1:
        s = s.title()
    return s


def parse(text: str, today: date) -> list:
    source_url = ''
    for line in text.split('\n')[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break

    # map char offset -> (month, year) using the most recent "# Month, Year" heading
    headings = [(m.start(), _month_from_str(m.group(1)), int(m.group(2)))
                for m in MONTH_HEADING_RE.finditer(text)]

    def context_for(pos):
        month = year = None
        for start, m, y in headings:
            if start <= pos:
                month, year = m, y
            else:
                break
        return month, year

    events = []
    for m in EVENT_RE.finditer(text):
        month, year = context_for(m.start())
        if not month:
            continue
        day1 = int(m.group(1))
        day2 = int(m.group(2)) if m.group(2) else None
        title = _clean_title(m.group(3))
        url = m.group(4).strip()
        venue = m.group(5).strip()

        try:
            start = date(year, month, day1)
        except ValueError:
            continue
        end = None
        if day2:
            try:
                end = date(year, month, day2)
            except ValueError:
                end = None

        ev = {
            't': title,
            'd': start.isoformat(),
            'v': venue or 'Likeminds',
            'u': url or source_url,
            'c': 'theatre',
            's': 'likeminds',
        }
        if end and end != start:
            ev['ed'] = end.isoformat()
        events.append(ev)

    window_end = today + timedelta(days=120)
    out = []
    for ev in events:
        d = date.fromisoformat(ev['d'])
        ed = date.fromisoformat(ev['ed']) if 'ed' in ev else d
        if ed >= today and d <= window_end:
            out.append(ev)
    return out
