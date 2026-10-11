"""Parser for Stichting Aralez events page (txt/aralez.md).

The page is a long free-text list of past and future events with no
consistent structure; the only reliably-parseable part is the
"***Upcoming:***" ... "***Past:***" block, where each event is one
paragraph starting with one or more **bold** title fragments followed by
"Period: ..." or "Date: ..." free text.
"""
import calendar
import re
from datetime import date, timedelta

MONTHS = {
    'januari': 1, 'january': 1, 'februari': 2, 'february': 2, 'maart': 3,
    'march': 3, 'april': 4, 'mei': 5, 'may': 5, 'juni': 6, 'june': 6,
    'juli': 7, 'july': 7, 'augustus': 8, 'august': 8, 'september': 9,
    'oktober': 10, 'october': 10, 'november': 11, 'december': 12,
}

BOLD_RE = re.compile(r'\*\*(.*?)\*\*')
PERIOD_RANGE_RE = re.compile(
    r'Period:\s*([A-Za-zë]+)\s*-\s*([A-Za-zë]+)\s*(\d{4})', re.IGNORECASE)
DATE_SINGLE_RE = re.compile(
    r'Date:\s*(\d{1,2})\w*\s*of\s*([A-Za-zë]+)\s*(\d{4})', re.IGNORECASE)
TIME_RANGE_RE = re.compile(r'(\d{1,2}:\d{2})\s*(?:-|and)\s*(\d{1,2}:\d{2})')
LOCATION_RE = re.compile(r'location:\s*([^,\.]+)', re.IGNORECASE)
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def _month_from_str(s):
    return MONTHS.get(s.lower())


def parse(text: str, today: date) -> list:
    source_url = ''
    for line in text.split('\n')[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break

    try:
        start = text.index('Upcoming:')
    except ValueError:
        return []
    try:
        end = text.index('Past:', start)
    except ValueError:
        end = len(text)
    section = text[start:end]

    paragraphs = [p.strip() for p in section.split('\n\n') if p.strip()]

    events = []
    for para in paragraphs:
        bolds = BOLD_RE.findall(para)
        if not bolds:
            continue
        title_parts = []
        venue = None
        for b in bolds:
            if b.lower().startswith('x '):
                venue = f"{b[2:].strip()} (Aralez)"
                continue
            title_parts.append(b.strip())
        title = ' '.join(title_parts).strip()
        if not title:
            continue

        start_date = end_date = None
        rm = PERIOD_RANGE_RE.search(para)
        if rm:
            m1 = _month_from_str(rm.group(1))
            m2 = _month_from_str(rm.group(2))
            yr = int(rm.group(3))
            if m1 and m2:
                try:
                    start_date = date(yr, m1, 1)
                    last_day = calendar.monthrange(yr, m2)[1]
                    end_date = date(yr, m2, last_day)
                except ValueError:
                    start_date = None
        if start_date is None:
            sm = DATE_SINGLE_RE.search(para)
            if sm:
                m1 = _month_from_str(sm.group(2))
                if m1:
                    try:
                        start_date = date(int(sm.group(3)), m1, int(sm.group(1)))
                    except ValueError:
                        start_date = None
        if start_date is None:
            continue

        tm = TIME_RANGE_RE.search(para)
        time1 = tm.group(1) if tm else None
        time2 = tm.group(2) if tm else None

        if venue is None:
            lm = LOCATION_RE.search(para)
            if lm:
                venue = lm.group(1).strip()
        venue = venue or 'Aralez'

        url = source_url
        links = LINK_RE.findall(para)
        for link_text, link_url in links:
            if 'info' in link_text.lower():
                url = link_url
                break
        else:
            if links:
                url = links[0][1]

        ev = {
            't': title,
            'd': start_date.isoformat(),
            'v': venue,
            'u': url,
            'c': 'workshop',
            's': 'aralez',
        }
        if end_date and end_date != start_date:
            ev['ed'] = end_date.isoformat()
        if time1:
            ev['h'] = time1
        if time2:
            ev['eh'] = time2
        events.append(ev)

    window_end = today + timedelta(days=120)
    out = []
    for ev in events:
        d = date.fromisoformat(ev['d'])
        ed = date.fromisoformat(ev['ed']) if 'ed' in ev else d
        if ed >= today and d <= window_end:
            out.append(ev)
    return out
