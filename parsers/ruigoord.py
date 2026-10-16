"""Parser for Ruigoord's iCal feed (https://ruigoord.nl/programma/lijst/?ical=1, saved as _data/ruigoord.ics).

The agenda page itself hides the titles from our HTML-to-markdown step, so we read the calendar feed instead.
Entries that run for more than a month (e.g. the season-long Sunday tea garden) are skipped: they are a standing
programme, not an event you can put in a calendar.
"""
import re
from datetime import date, datetime, timedelta

try:
    from _price import from_text as price_from_text
except ImportError:
    from parsers._price import from_text as price_from_text

BASE = "https://ruigoord.nl"


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def _unesc(s):
    return re.sub(r"\\([,;\\])", r"\1", s.replace("\\n", " ").replace("\\N", " ")).strip()


def _stamp(val):
    m = re.search(r"(\d{4})(\d\d)(\d\d)(?:T(\d\d)(\d\d))?", val)
    if not m:
        return None, None
    d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return d, (f"{m.group(4)}:{m.group(5)}" if m.group(4) else None)


def _category(title):
    t = title.lower()
    if re.search(r"expositie|exhibition|tentoonstelling", t):
        return "exhibition"
    if re.search(r"trance|party|feest|\bbal\b|dance|\bdj\b|techno|rave|ballonnenfeest", t):
        return "club"
    if re.search(r"ruigkids|kids|kinder", t):
        return "kids"
    if re.search(r"concert|live|muziek|music|band|jam|huun|silk road", t):
        return "music"
    if re.search(r"ceremonie|drumcirkel|bliss", t):
        return "community"
    if re.search(r"woord|poëzie|poezie|lezing|talk|spoken", t):
        return "talk"
    if re.search(r"workshop|cursus|academie", t):
        return "workshop"
    return "other"


def parse(text, today):
    out = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", _unfold(text), re.S):
        f = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            f.setdefault(k.split(";")[0], v)
        d, h = _stamp(f.get("DTSTART", ""))
        ed, eh = _stamp(f.get("DTEND", ""))
        title = _unesc(f.get("SUMMARY", ""))
        if not d or not title:
            continue
        if ed and (ed - d).days > 31:
            continue
        if (ed or d) < today or d > today + timedelta(days=240):
            continue
        e = {"t": title, "d": d.isoformat(), "v": "Ruigoord", "c": _category(title), "s": "ruigoord",
             "u": f.get("URL") or BASE + "/programma/"}
        if h and h != "00:00":
            e["h"] = h
            if eh and ed == d and eh != h:
                e["eh"] = eh
        overnight = ed and (ed - d).days == 1 and eh and eh <= "12:00"
        if overnight:
            e["eh"] = eh
        elif ed and ed > d and (ed - d).days <= 31:
            e["ed"] = ed.isoformat()
        desc = _unesc(f.get("DESCRIPTION", ""))
        desc = re.sub(r"^(?:kaarten|tickets|evenementen|binnenkort beschikbaar)\s+(?:evenementen\s+)?", "", desc, flags=re.I)
        price = price_from_text(desc)
        if price:
            e["p"] = price
        if desc:
            e["b"] = (desc[:157] + "...") if len(desc) > 160 else desc
        out.append(e)
    return out
