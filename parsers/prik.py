"""Parser for Prik (prikamsterdam.nl, markdown dump of the home page 'Coming up' list).

Each listed night links to /event-details/<slug>-YYYY-MM-DD-HH-MM, which gives the date and start time. Items tagged
'Every week' only show their next date, so they are repeated weekly for the next 8 weeks. Other items are single dates.
"""
import re
from datetime import date, timedelta

HORIZON = 56
ITEM = re.compile(
    r"(?:\*\s*(Every week)\s*\n+\s*)?\[([^\]\n]+)\]\((https://www\.prikamsterdam\.nl/event-details/[^)]*?-(20\d\d)-(\d\d)-(\d\d)-(\d\d)-(\d\d))\)(.*?)(?=\n\*\s|\nOur pics|\Z)",
    re.S)


def _cat(t):
    t = t.lower()
    if re.search(r"karaoke|trashy|music|dj|live", t):
        return "music"
    if re.search(r"gaming|game|quiz|bingo", t):
        return "community"
    if re.search(r"drag|show", t):
        return "other"
    return "other"


def parse(text, today):
    out, seen = [], set()
    for m in ITEM.finditer(text):
        weekly, title, url, y, mo, d, hh, mm, rest = m.groups()
        if url in seen:
            continue
        seen.add(url)
        title = title.strip().rstrip("!").strip()
        try:
            start = date(int(y), int(mo), int(d))
        except ValueError:
            continue
        blurb = " ".join(l.strip() for l in rest.splitlines()
                         if l.strip() and not re.match(r"(?:\[Learn more\]|(?:ma|di|wo|do|vr|za|zo)\s+\d|Amsterdam$)", l.strip(), re.I))
        base = {"t": title, "c": _cat(title), "v": "Prik", "u": url, "s": "prik", "h": f"{hh}:{mm}", "addr": "Spuistraat 109"}
        if blurb:
            base["b"] = blurb[:160]
        dates = [start]
        if weekly:
            dates = [start + timedelta(days=7 * k) for k in range(HORIZON // 7 + 1)]
        for dd in dates:
            if today <= dd <= today + timedelta(days=HORIZON if weekly else 240):
                out.append(dict(base, d=dd.isoformat()))
    return out
