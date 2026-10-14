"""Parser for Museum Ons' Lieve Heer op Solder (opsolder.nl/agenda, markdown dump).

Sections 'NU TE ZIEN' and 'BINNENKORT TE ZIEN' are read, 'WAS TE ZIEN' is ignored. Every item appears as
  <title> / <type> / <title again> / <date text>
Dates are free text: '22, 23 & 24 oktober 2026 van 19.00 – 21.00 uur', 'Op zaterdag 7 november 2026',
'21 oktober 2026 t/m 24 oktober 2027', 'Te zien tot eind 2026'. Items without a date (regular masses) are skipped.
"""
import re
from datetime import date, timedelta

try:
    from _dates import find_dates, lead_days, span, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates, lead_days, span, hhmm

URL = "https://opsolder.nl/agenda/"
VENUE = "Museum Ons' Lieve Heer op Solder"


def _items(lines):
    i = 0
    while i < len(lines) - 2:
        if lines[i + 2] == lines[i] and lines[i + 1] not in ("---",) and len(lines[i + 1]) < 30:
            title, typ = lines[i], lines[i + 1]
            j = i + 3
            date_line = lines[j] if j < len(lines) and lines[j] != "---" else ""
            yield title, typ, date_line
            i = j + 1
        else:
            i += 1


def parse(text, today):
    m = re.search(r"###\s*NU TE ZIEN(.*?)(?=###\s*WAS TE ZIEN|\Z)", text, re.S)
    if not m:
        return []
    lines = [l.strip() for l in m.group(1).splitlines() if l.strip()]
    lines = [l for l in lines if not l.startswith("###")]
    out = []
    for title, typ, dl in _items(lines):
        times = re.search(r"(\d{1,2}[.:]\d{2})\s*[–-]\s*(\d{1,2}[.:]\d{2})", dl)
        h, eh = (hhmm(times.group(1)), hhmm(times.group(2))) if times else (None, None)
        e0 = {"t": title, "v": VENUE, "u": URL, "s": "opsolder"}
        if re.search(r"\bdj\b", title, re.I):
            e0["c"] = "club"
        # exhibition-like: ranges ('t/m'), 'te zien tot', presentations
        rng = re.search(r"\bt/m\b|\btot en met\b|\btot\b|\bte zien\b", dl, re.I)
        dates = find_dates(dl, today)
        if re.search(r"te zien tot eind (20\d\d)", dl, re.I):
            y = int(re.search(r"eind (20\d\d)", dl).group(1))
            sp = span(None, date(y, 12, 31), today)
            if sp:
                e = dict(e0, t=title, c="exhibition", d=sp[0].isoformat())
                if sp[1]:
                    e["ed"] = sp[1].isoformat()
                out.append(e)
            continue
        if rng and len(dates) >= 2 and (dates[-1] - dates[0]).days > 3:
            sp = span(dates[0], dates[-1], today)
            if sp:
                e = dict(e0, c="exhibition", d=sp[0].isoformat())
                if sp[1]:
                    e["ed"] = sp[1].isoformat()
                out.append(e)
            continue
        days = lead_days(dl, today) or dates
        for d in days:
            if d < today or d > today + timedelta(days=240):
                continue
            e = dict(e0, d=d.isoformat())
            e.setdefault("c", "community" if re.search(r"museumnacht", title, re.I) else "other")
            if h:
                e["h"] = h
                if eh:
                    e["eh"] = eh
            out.append(e)
    return out
