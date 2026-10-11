"""Parser for Filmhuis Cavia monthly programme pages (txt/cavia_sep.md, txt/cavia_okt.md).

Each input file is a single month's programme, rendered from
https://www.filmhuiscavia.nl/programma/<month>-<year>. Events are laid out as
blocks separated by '---' lines, each with a bold date/time line, a category
badge, one or more markdown headings for the title, and body text possibly
containing a "MEER→"/"MORE→" link to a dedicated event page.
"""
import re
from datetime import date, timedelta

MONTHS_NL = {
    'januari': 1, 'februari': 2, 'maart': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'augustus': 8, 'september': 9, 'oktober': 10, 'november': 11,
    'december': 12,
}

DATE_RE = re.compile(
    r'\*\*(?:[A-Za-zë]+\.?\s+)?(\d{1,2})\s*(?:-\s*(\d{1,2}))?\s+'
    r'([A-Za-zëé]+)(?:,\s*(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?)?\*\*'
)
LINK_RE = re.compile(r'\[\*{0,2}\s*(?:MEER|MORE)\s*→\s*\*{0,2}\]\(([^)]+)\)', re.IGNORECASE)
HEADING_RE = re.compile(r'^(#{2,3})\s+(.*)$')

STOP_PREFIXES = {'premiere', 'première', 'special'}


def _month_from_str(s):
    s = s.lower()
    for name, num in MONTHS_NL.items():
        if s.startswith(name[:3]):
            return num
    return None


def _infer_year(month, day, today):
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=45):
            return y
    return today.year


def _clean_text(s):
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = re.sub(r'\*\*|\*|__', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'^\]+', '', s).strip()
    s = re.sub(r'\b(TICKETS|MORE INFO|MEER INFO)\b', '', s, flags=re.IGNORECASE).strip()
    return s


def _build_title(heading_lines):
    if not heading_lines:
        return None
    h2_idx = next((i for i, (lvl, _t) in enumerate(heading_lines) if lvl == 2), None)
    if h2_idx is None:
        return _clean_text(heading_lines[0][1])
    main = _clean_text(heading_lines[h2_idx][1])
    prefix = None
    for lvl, txt in heading_lines[:h2_idx]:
        if lvl == 3:
            prefix = _clean_text(txt)
            break
    suffix = None
    if h2_idx + 1 < len(heading_lines) and heading_lines[h2_idx + 1][0] == 3:
        suffix = _clean_text(heading_lines[h2_idx + 1][1])
    title = main
    if prefix:
        low = prefix.lower()
        if not any(low == sp or low.startswith(sp) for sp in STOP_PREFIXES):
            if 'screening' in low or 'fundraising' in low:
                title = f"{main} {prefix}"
            else:
                title = f"{prefix}: {main}"
    if suffix:
        title = f"{title} {suffix}"
    return title


def parse(text: str, today: date) -> list:
    events = []
    lines = text.split('\n')

    source_url = ''
    for line in lines[:5]:
        if line.startswith('SOURCE:'):
            source_url = line.split('SOURCE:', 1)[1].strip()
            break

    blocks = []
    current = []
    for line in lines:
        if line.strip() == '---':
            if current:
                blocks.append(current)
            current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    for block in blocks:
        block_text = '\n'.join(block)
        if 'Toegang' in block_text or 'Reserveren' in block_text:
            continue
        if not DATE_RE.search(block_text):
            continue

        heading_lines = []
        started = False
        for l in block:
            hm = HEADING_RE.match(l.strip())
            if hm:
                heading_lines.append((len(hm.group(1)), hm.group(2).strip()))
                started = True
            elif started and l.strip() != '':
                break
        title = _build_title(heading_lines)
        if not title:
            continue

        um = LINK_RE.search(block_text)
        url = um.group(1) if um else source_url

        price = '€5'
        if re.search(r'donation|donatie', block_text, re.IGNORECASE):
            price = 'donation'

        for d1s, d2s, mstr, t1, t2 in DATE_RE.findall(block_text):
            mo = _month_from_str(mstr)
            if not mo:
                continue
            d1 = int(d1s)
            yr = _infer_year(mo, d1, today)
            try:
                start = date(yr, mo, d1)
            except ValueError:
                continue
            end = None
            if d2s:
                try:
                    end = date(yr, mo, int(d2s))
                except ValueError:
                    end = None

            ev = {
                't': title,
                'd': start.isoformat(),
                'v': 'Filmhuis Cavia',
                'u': url,
                'c': 'film',
                's': 'cavia',
                'p': price,
            }
            if end and end != start:
                ev['ed'] = end.isoformat()
            if t1:
                ev['h'] = t1
            if t2:
                ev['eh'] = t2
            events.append(ev)

    window_end = today + timedelta(days=120)
    out = []
    for ev in events:
        d = date.fromisoformat(ev['d'])
        ed = date.fromisoformat(ev['ed']) if 'ed' in ev else d
        if ed >= today and d <= window_end:
            out.append(ev)
    return out
