"""Parser for De VerbroederIJ (verbroederij.nl agenda, markdown dump).

The agenda is mostly weekly daytime classes (yoga, gardening, Zumba, chi kung). Those are filtered out; evening
shows, parties, workshops and information evenings stay.
"""
import re
from datetime import date, timedelta

try:
    from _dates import MONTHS, make_date
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date

ITEM = re.compile(
    r"\[(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\s*\n\s*(\d{1,2})\s+([a-z]+)\.?\s*\n\s*(\d{1,2}:\d{2})\s*\n"
    r"\*\s*([^\n]+)\n\s*###\s*([^\n]+)\n(.*?)\]\((https?://[^)]+)\)",
    re.S | re.I,
)
# weekly classes and daytime community sessions that are not events to go out to
SKIP_TAG = re.compile(r"yoga|sportles|tuinier|mediter|buiten|training|zumba|beweg|chi kung", re.I)
SKIP_TITLE = re.compile(r"yoga|zumba|chi kung|moestuin|bewegerij|mindful|zagerij", re.I)


def _category(tag, title):
    t = (tag + " " + title).lower()
    if "dj" in t or "dansfeest" in t:
        return "club"
    if "comedy" in t or "stand-up" in t:
        return "comedy"
    if "workshop" in t or "kunstclub" in t:
        return "workshop"
    if "informatie" in t or "bijeenkomst" in t or "socratisch" in t:
        return "talk"
    if "muziek" in t or "concert" in t or "live" in t:
        return "music"
    return "community"


def parse(text, today):
    out, seen = [], set()
    for m in ITEM.finditer(text):
        day, mon, hm, tag, title, body, url = m.groups()
        mo = MONTHS.get(mon.lower())
        if not mo:
            continue
        d = make_date(int(day), mo, None, today)
        if not d or d < today or d > today + timedelta(days=200):
            continue
        title = title.strip()
        if SKIP_TAG.search(tag) or SKIP_TITLE.search(title):
            continue
        key = (d, title.lower())
        if key in seen:
            continue
        seen.add(key)
        desc = re.sub(r"\s+", " ", re.sub(r"\*\*|…|\.\.\.", "", body.replace("\n", " "))).strip()
        e = {"t": title, "d": d.isoformat(), "h": hm, "v": "De VerbroederIJ", "u": url, "s": "verbroederij",
             "c": _category(tag, title)}
        if "gratis" in tag.lower():
            e["p"] = "Free"
        if desc:
            e["b"] = desc[:160]
        out.append(e)
    return out
