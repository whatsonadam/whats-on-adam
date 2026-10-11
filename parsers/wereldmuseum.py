"""Parser for Wereldmuseum Amsterdam (txt/wereldmuseum.md).

Only the "Nu te zien en te doen" section carries explicit dates, as
`### Title` / `[Link](relative-url)` / optional date-range line. The earlier
"Agenda" teaser list of plain links has no dates at all and is skipped
(per spec: never invent a date).
"""
import re
from datetime import date, timedelta

MONTHS = {
    'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12,
}

DATE_PART = r'(\d{1,2})\s+([A-Za-z]+)\.?(?:\s+(\d{4}))?'
DATE_RANGE_RE = re.compile(DATE_PART + r'(?:\s+t/m\s+' + DATE_PART + r')?')

BLOCK_RE = re.compile(
    r'^#{1,3}\s+(.+?)\s*\n\n\[Link\]\(([^)]+)\)\n\n([^\n#]*)', re.MULTILINE)


def _month_from_str(s):
    return MONTHS.get(s.lower()[:3])


def _infer_year(month, day, today, other=None):
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=45):
            return y
    return today.year


def _guess_category(title, url):
    low_t = title.lower()
    low_u = url.lower()
    if 'tentoonstelling' in low_u:
        return 'exhibition'
    if 'disco' in low_t or 'ade' in low_t.split():
        return 'club'
    return 'other'


def parse(text: str, today: date) -> list:
    source_url = ''
    for line in text.split('\n')[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break
    base = 'https://amsterdam.wereldmuseum.nl'

    try:
        end = text.index('Altijd gratis te doen')
    except ValueError:
        end = len(text)
    section = text[:end]

    events = []
    for m in BLOCK_RE.finditer(section):
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        url_rel = m.group(2).strip()
        date_line = m.group(3).strip()

        dm = DATE_RANGE_RE.search(date_line)
        if not dm:
            continue
        d1, m1s, y1, d2, m2s, y2 = dm.groups()
        month1 = _month_from_str(m1s)
        if not month1:
            continue
        day1 = int(d1)
        year1 = int(y1) if y1 else _infer_year(month1, day1, today)
        try:
            start_date = date(year1, month1, day1)
        except ValueError:
            continue

        end_date = None
        if d2 and m2s:
            month2 = _month_from_str(m2s)
            day2 = int(d2)
            if month2:
                if y2:
                    year2 = int(y2)
                elif month2 >= month1:
                    year2 = year1
                else:
                    year2 = year1 + 1
                try:
                    end_date = date(year2, month2, day2)
                except ValueError:
                    end_date = None

        url = base + url_rel if url_rel.startswith('/') else url_rel

        ev = {
            't': title,
            'd': start_date.isoformat(),
            'v': 'Wereldmuseum Amsterdam',
            'u': url,
            'c': _guess_category(title, url),
            's': 'wereldmuseum',
        }
        if end_date and end_date != start_date:
            ev['ed'] = end_date.isoformat()
        events.append(ev)

    window_end = today + timedelta(days=120)
    out = []
    for ev in events:
        d = date.fromisoformat(ev['d'])
        ed = date.fromisoformat(ev['ed']) if 'ed' in ev else d
        if ed >= today and d <= window_end:
            out.append(ev)
    return out
