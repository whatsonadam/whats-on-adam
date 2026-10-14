"""Small date helpers shared by the newer parsers (Dutch and English month names, no year on the page)."""
import re
from datetime import date, timedelta

MONTHS = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2, "mar": 3, "maart": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "mei": 5, "jun": 6, "juni": 6, "june": 6, "jul": 7, "juli": 7, "july": 7,
    "aug": 8, "augustus": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "okt": 10, "oktober": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
WEEKDAYS = {"ma": 0, "maandag": 0, "mon": 0, "monday": 0, "di": 1, "dinsdag": 1, "tue": 1, "tuesday": 1,
            "wo": 2, "woensdag": 2, "wed": 2, "wednesday": 2, "do": 3, "donderdag": 3, "thu": 3, "thursday": 3,
            "vr": 4, "vrijdag": 4, "fri": 4, "friday": 4, "za": 5, "zaterdag": 5, "sat": 5, "saturday": 5,
            "zo": 6, "zondag": 6, "sun": 6, "sunday": 6}

_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
# "17 oktober", "17th of October", "17 Oct 2026"   and   "October 17", "October 17th, 2026"
_DM = re.compile(rf"(?<![\d.:])(\d{{1,2}})(?:st|nd|rd|th|e)?\.?\s+(?:of\s+)?({_MONTH_RX})\b\.?(?:\s+(20\d\d))?", re.I)
_MD = re.compile(rf"\b({_MONTH_RX})\b\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(20\d\d))?", re.I)


def infer_year(month, day, today, back_days=45):
    """The year that puts month/day closest to today, allowing for events a bit in the past."""
    for y in (today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if d >= today - timedelta(days=back_days):
            return y
    return today.year


def make_date(day, month, year, today):
    try:
        return date(int(year) if year else infer_year(month, day, today), month, day)
    except ValueError:
        return None


def find_dates(text, today):
    """All dates mentioned in a phrase, in order. Handles '22, 23 & 24 oktober 2026', '9 oktober t/m 29 oktober', 'October 29 to November 8'."""
    hits = []
    for m in _DM.finditer(text):
        hits.append((m.start(), int(m.group(1)), MONTHS[m.group(2).lower()], m.group(3), m.end()))
    for m in _MD.finditer(text):
        # skip "<month> <day>" matches that are really the tail of a "<day> <month> <year>" phrase
        if any(h[0] <= m.start() < h[4] for h in hits):
            continue
        hits.append((m.start(), int(m.group(2)), MONTHS[m.group(1).lower()], m.group(3), m.end()))
    hits.sort()
    out = []
    for i, (pos, day, mon, yr, end) in enumerate(hits):
        if not yr:   # "22, 23 & 24 oktober": the earlier days share the month of the last one, handled by caller if needed
            yr = None
        out.append(make_date(day, mon, yr, today))
    return [d for d in out if d]


def lead_days(text, today):
    """'22, 23 & 24 oktober 2026' -> the extra leading day numbers (22, 23) that share the month of the 24th."""
    m = re.search(rf"((?:\d{{1,2}}\s*(?:,|&|en|and)\s*)+)(\d{{1,2}})\s+({_MONTH_RX})\b\.?(?:\s+(20\d\d))?", text, re.I)
    if not m:
        return []
    mon = MONTHS[m.group(3).lower()]
    days = [int(x) for x in re.findall(r"\d{1,2}", m.group(1))] + [int(m.group(2))]
    return [d for d in (make_date(x, mon, m.group(4), today) for x in days) if d]


def hhmm(s):
    """'19.00' / '19:00' / '7 pm' -> '19:00' (None if it is not a time)."""
    m = re.fullmatch(r"\s*(\d{1,2})[.:](\d{2})\s*", s or "")
    if not m or int(m.group(1)) > 24 or int(m.group(2)) > 59:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def in_window(d, today, days=240):
    return today - timedelta(days=0) <= d <= today + timedelta(days=days)


def span(start, end, today):
    """For ongoing exhibitions: show from today until the end date. Returns (d, ed) or None if over."""
    if end and end < today:
        return None
    d = max(start, today) if start else today
    return d, (end if end and end > d else None)
