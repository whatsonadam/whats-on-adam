"""Parser for theater.nl opera listing for Amsterdam (markdown dump of ?start=0,10,20... pages joined together).

Each performance is a date block ('vrijdag / 16 okt 2026 / Aanvang: 16:00 / Amsterdam') followed by its '### Title',
a bold company line, a blurb and a 'genres - price' line. The listing names no venue, so only productions by
De Nationale Opera / Het Nationale Ballet are kept: those play at the Nationale Opera & Ballet (Amstel 3).
"""
import re
from datetime import timedelta

try:
    from _dates import MONTHS, make_date, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date, hhmm

ITEM = re.compile(
    r"(\d{1,2})\s+([a-z]{3,9})\s+(20\d\d)\s+Aanvang:\s+(\d{1,2}:\d{2})(.*?)###\s+([^\n]+)\n\s*\n\*\*([^*]+)\*\*\n\s*\n([^\n]*)\n\s*\n([^\n]*)",
    re.S | re.I)
KEEP = re.compile(r"nationale opera|nationale ballet", re.I)


def parse(text, today):
    out, seen = [], set()
    for m in ITEM.finditer(text):
        day, mon, year, tm, _mid, title, company, blurb, genres = m.groups()
        mo = MONTHS.get(mon.lower()) or (3 if mon.lower() == "mrt" else None)
        if not mo or not KEEP.search(title + " " + company):
            continue
        d = make_date(int(day), mo, int(year), today)
        if not d or d < today or d > today + timedelta(days=240):
            continue
        key = (title, d, tm)
        if key in seen:
            continue
        seen.add(key)
        title = re.sub(r"\s*-\s*De Nationale Opera\s*$", "", title.strip(), flags=re.I)
        g = genres.lower()
        if re.search(r"kinder|jeugd|familie", g):
            cat = "kids"
        elif re.search(r"\bdans\b", g) and "opera" not in g:
            cat = "dance"
        else:
            cat = "music"
        e = {"t": title, "d": d.isoformat(), "h": hhmm(tm), "c": cat, "v": "Nationale Opera & Ballet",
             "u": "https://www.theater.nl/voorstellingen/opera/amsterdam", "s": "theaternl", "addr": "Amstel 3",
             "b": re.sub(r"\s+", " ", blurb).strip()[:160]}
        p = re.search(r"€\s?(\d+)(?:,(\d{2}))?", genres)
        if p:
            e["p"] = f"€{p.group(1)},{p.group(2)}" if p.group(2) else f"€{p.group(1)}"
        out.append(e)
    return out
