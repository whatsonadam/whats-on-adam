"""Parser for Marineterrein Amsterdam (marineterrein.nl/agenda, markdown dump).

Cards look like '* [## Title / date line(s) / place](url)'. Two kinds:
  one-off      'di 20 oktober'            -> one event
  weekly runs  't/m ma 28 december' + 'Elke maandagavond' -> one event per matching weekday until the end date
Cards that say 'Meerdere dagen' or 'wisselende dagen' have no dates we can read and are skipped.
The agenda gives no start times.
"""
import re
from datetime import date, timedelta

try:
    from _dates import WEEKDAYS, find_dates
except ImportError:  # pragma: no cover
    from parsers._dates import WEEKDAYS, find_dates

HORIZON = 56  # days of a weekly series to list

CARD = re.compile(r"\*\s*\[##\s*([^\n]+)\n(.*?)\]\((https://marineterrein\.nl/agenda/[^)]+)\)", re.S)


def _category(title):
    t = title.lower()
    if re.search(r"quiz|kledingruil|rondleiding", t):
        return "community"
    if re.search(r"zingen|concert|gong|klank|groove|muziek", t):
        return "music"
    if re.search(r"workshop|atelier", t):
        return "workshop"
    if re.search(r"weerbare stad|bioblitz|debat|lezing", t):
        return "talk"
    return "other"


def parse(text, today):
    out = []
    for m in CARD.finditer(text):
        title, rest, url = m.group(1).strip(), m.group(2), m.group(3)
        lines = [l.strip() for l in rest.splitlines() if l.strip()]
        joined = " ".join(lines)
        if re.search(r"meerdere dagen|wisselende dagen", joined, re.I):
            continue
        place = lines[-1] if lines and not re.search(r"\d|elke|t/m|iedere", lines[-1], re.I) else ""
        base = {"t": title, "c": _category(title), "v": "Marineterrein" + (f" · {place}" if place else ""), "u": url,
                "s": "marineterrein"}
        weekly = re.search(r"\b(?:elke|iedere)\s+((?:ma|di|woens|donder|vrij|zater|zon)[a-z]*)", joined, re.I)
        if weekly:
            end = find_dates(re.sub(r"^.*?t/m", "", joined), today)
            end = end[0] if end else None
            days = set()
            for w in re.findall(r"(maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)", joined, re.I):
                days.add(WEEKDAYS[w.lower()])
            if not days:
                continue
            limit = min(today + timedelta(days=HORIZON), end) if end else today + timedelta(days=HORIZON)
            d = today
            while d <= limit:
                if d.weekday() in days:
                    out.append(dict(base, d=d.isoformat()))
                d += timedelta(days=1)
            continue
        dates = find_dates(joined, today)
        if not dates:
            continue
        d = dates[0]
        if d < today or d > today + timedelta(days=240):
            continue
        out.append(dict(base, d=d.isoformat()))
    return out
