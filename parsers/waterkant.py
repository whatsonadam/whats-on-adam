"""Parser for Waterkant (waterkantamsterdam.nl/agenda, markdown dump): the fortnightly pub quiz.

The page shows three headings in a row (time, dates, title), e.g.
  ## 18:00 - 21:00.   ## DI 03 NOV. / DI 17 NOV. / ...   ## Waterkant Pubquiz
followed by '**DI 03 NOV.** Theme.' lines and a '€3,75 p.p.' price.
"""
import re
from datetime import timedelta

try:
    from _dates import make_date, MONTHS, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import make_date, MONTHS, hhmm

URL = "https://www.waterkantamsterdam.nl/agenda"
DAY = re.compile(r"(?:MA|DI|WO|DO|VR|ZA|ZO)\s+(\d{1,2})\s+([A-Z]{3,9})\.?", re.I)


def parse(text, today):
    heads = [h.strip() for h in re.findall(r"^##[ \t]*(.*)$", text, re.M)]
    heads = [h for h in heads if h]
    out = []
    for i, h in enumerate(heads[:-2]):
        t = re.match(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", h)
        if not t or not DAY.search(heads[i + 1]):
            continue
        title = heads[i + 2].strip(" .")
        themes = {}
        for m in re.finditer(r"\*\*((?:MA|DI|WO|DO|VR|ZA|ZO)\s+\d{1,2}\s+[A-Z]{3,9}\.?)\*\*\s*([^\n]+)", text, re.I):
            themes[re.sub(r"\W+", "", m.group(1)).lower()] = m.group(2).strip(" .")
        price = re.search(r"€\s?(\d+[.,]\d{2})\s*p\.?p", text)
        for m in DAY.finditer(heads[i + 1]):
            mon = MONTHS.get(m.group(2).lower()[:3])
            d = make_date(int(m.group(1)), mon, None, today) if mon else None
            if not d or d < today or d > today + timedelta(days=240):
                continue
            key = re.sub(r"\W+", "", m.group(0)).lower()
            e = {"t": title, "d": d.isoformat(), "h": hhmm(t.group(1)), "eh": hhmm(t.group(2)), "v": "Waterkant",
                 "c": "other", "u": URL, "s": "waterkant"}
            if themes.get(key):
                e["b"] = "Theme: " + themes[key]
            if price:
                e["p"] = "€" + price.group(1).replace(".", ",")
            out.append(e)
    return out
