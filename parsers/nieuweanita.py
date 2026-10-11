"""Parser for de Nieuwe Anita (txt/nieuweanita.md).

The page has a short "featured" teaser section near the top (with a few
events and their ticket-page URLs) followed by a full "# Agenda" listing of
"## Title" / "D Mon" / optional start+end time blocks with no URLs. We parse
the Agenda listing (it's the complete list) and use the featured section only
to recover per-event URLs where available, falling back to the page URL.
"""
import re
from datetime import date, timedelta

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

DATE_RE = re.compile(r'^(\d{1,2})\s+([A-Za-z]+)$|^([A-Za-z]+)\s+(\d{1,2})$')
TIME_RE = re.compile(r'^(\d{1,2}:\d{2})$')

CATEGORY_KEYWORDS = [
    (('cinemanita', 'fiber factory'), 'film'),
    (('popquiz', 'quiz'), 'other'),
    (('comedy', 'nutty anita', 'freak show', 'cabaret'), 'comedy'),
    (('party', 'disco', 'shake-out', 'beatclub'), 'club'),
    (('vinylbingo', 'bingo'), 'other'),
    (('impro', 'jam'), 'comedy'),
    (('literanita', 'smut slam', 'gember en citroenen'), 'other'),
    (('game developers',), 'community'),
    (('spelen', 'robin food'), 'community'),
]


def _month_from_str(s):
    s = s.lower()[:3]
    return MONTHS.get(s)


def _infer_year(month, day, today):
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=45):
            return y
    return today.year


def _clean_title(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s).strip()
    s = re.sub(r'\s*\]\s*$', '', s)
    return s


def _guess_category(title):
    low = title.lower()
    for keywords, cat in CATEGORY_KEYWORDS:
        if any(k in low for k in keywords):
            return cat
    return 'music'


def parse(text: str, today: date) -> list:
    lines = text.split('\n')

    source_url = ''
    for line in lines[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break

    # Build title -> url map from the featured teaser section (before "# Agenda").
    try:
        agenda_idx = next(i for i, l in enumerate(lines) if l.strip() == '# Agenda')
    except StopIteration:
        agenda_idx = 0

    url_map = {}
    heading = None
    for l in lines[:agenda_idx]:
        hm = re.match(r'^##\s+(.*)$', l.strip())
        if hm:
            heading = _clean_title(hm.group(1))
            continue
        lm = re.match(r'^\[MORE INFO\]\(([^)]+)\)$', l.strip(), re.IGNORECASE)
        if lm and heading:
            url_map[heading] = lm.group(1)

    events = []
    section = lines[agenda_idx:]
    i = 0
    n = len(section)
    while i < n:
        l = section[i].strip()
        hm = re.match(r'^##\s+(.*)$', l)
        if not hm:
            i += 1
            continue
        title = _clean_title(hm.group(1))
        i += 1
        # find date line (skip blanks)
        date_match = None
        while i < n:
            cand = section[i].strip()
            if cand == '':
                i += 1
                continue
            if cand.startswith('##'):
                break
            dm = DATE_RE.match(cand)
            if dm:
                date_match = dm
                i += 1
            break
        if not date_match:
            continue
        if date_match.group(1):
            day, mstr = int(date_match.group(1)), date_match.group(2)
        else:
            mstr, day = date_match.group(3), int(date_match.group(4))
        month = _month_from_str(mstr)
        if not month:
            continue

        # optional time lines follow (up to 2)
        times = []
        while i < n and len(times) < 2:
            cand = section[i].strip()
            if cand == '':
                i += 1
                continue
            tm = TIME_RE.match(cand)
            if tm:
                times.append(tm.group(1))
                i += 1
            else:
                break

        yr = _infer_year(month, day, today)
        try:
            d = date(yr, month, day)
        except ValueError:
            continue

        ev = {
            't': title,
            'd': d.isoformat(),
            'v': 'de Nieuwe Anita',
            'u': url_map.get(title, source_url),
            'c': _guess_category(title),
            's': 'nieuweanita',
        }
        if times:
            ev['h'] = times[0]
        if len(times) > 1:
            ev['eh'] = times[1]
        events.append(ev)

    window_end = today + timedelta(days=120)
    return [e for e in events if today <= date.fromisoformat(e['d']) <= window_end]
