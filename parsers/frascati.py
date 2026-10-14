"""Parser for Frascati theatre (frascatitheater.nl/nl/agenda, markdown dump).

Each production is '* [### Title' + company + date range + genres, followed by a 'Speeldata' list with one line per
performance ('+ wo 14 okt', time, optional 'Première'/'Try-out', hall). Past performances say 'Geweest'.
Every future performance becomes one event, with the price of the cheapest ticket when shown.
"""
import re
from datetime import timedelta

try:
    from _dates import MONTHS, make_date, hhmm
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date, hhmm

BASE = "https://www.frascatitheater.nl"
PERF = re.compile(r"\+\s*(?:ma|di|wo|do|vr|za|zo)\s+(\d{1,2})\s+([a-z]+)\s*\n\s*(\d{1,2}:\d{2})([^+]*)", re.I)


def parse(text, today):
    out = []
    for blk in re.split(r"\n\*\s*\[###\s*", text)[1:]:
        title = blk.split("\n", 1)[0].strip()
        company = (blk.split("\n")[1].strip() if "\n" in blk else "")
        link = re.search(r"\]\((/nl/agenda/[^)]+)\)", blk)
        url = BASE + link.group(1) if link else BASE + "/nl/agenda"
        genres = " ".join(re.findall(r"\+\s*\[([^\]]+)\]", blk)).lower()
        cat = "dance" if re.search(r"\bdans\b", genres) else ("music" if "muziektheater" in genres else "theatre")
        price = re.search(r"€\s?(\d+),(\d{2})", blk)
        for m in PERF.finditer(blk):
            day, mon, hm, rest = m.groups()
            mo = MONTHS.get(mon.lower()[:4]) or MONTHS.get(mon.lower()[:3])
            if not mo or "Geweest" in rest:
                continue
            d = make_date(int(day), mo, None, today)
            if not d or d < today or d > today + timedelta(days=240):
                continue
            e = {"t": title, "d": d.isoformat(), "h": hhmm(hm), "v": "Frascati", "c": cat, "u": url, "s": "frascati"}
            note = []
            if re.search(r"première", rest, re.I):
                note.append("Premiere")
            if re.search(r"try-out", rest, re.I):
                note.append("Try-out")
            if company:
                note.append(company)
            if note:
                e["b"] = " · ".join(note)[:160]
            if price and "uitverkocht" not in rest:
                e["p"] = f"€{price.group(1)},{price.group(2)}"
            if "Nederlands gesproken" in genres and not re.search(r"engels gesproken|language no problem", genres):
                e["nl"] = 1
            elif re.search(r"engels gesproken|language no problem", genres):
                e["en"] = 1
            out.append(e)
    return out
