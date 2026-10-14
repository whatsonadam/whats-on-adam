"""Parser for the Amsterdam Museum agenda (amsterdammuseum.nl/en/see-and-do/agenda, markdown dump).

Two kinds of cards:
  Exhibitions     '[Title](url)Exhibitions / blurb / Until 21 Oct in **[Place](..)**' (or 'From 7 Mar 2027 in ...')
  Public Program  '[Title](url)Public Program / blurb / 14 Oct, 21 Oct & 9 Dec 2026 in **[Place](..)**'
The list gives no start times. Cards without dates (permanent displays, open calls) are skipped.
"""
import re
from datetime import timedelta

try:
    from _dates import find_dates, span
except ImportError:  # pragma: no cover
    from parsers._dates import find_dates, span

CARD = re.compile(
    r"\[([^\]]+)\]\((https://www\.amsterdammuseum\.nl/en/(exhibition|public-program)/[^)]+)\)[^\n]*\n(.*?)(?=\n\[[^\]]+\]\(https://www\.amsterdammuseum|\nParticipation|\nUpcoming|\Z)",
    re.S,
)


def _place(body):
    m = re.search(r"\bin \*\*\[([^\]]+)\]", body)
    return m.group(1) if m else ""


def parse(text, today):
    out, seen = [], set()
    for m in CARD.finditer(text):
        title, url, kind, body = m.groups()
        title = re.sub(r"\s*-\s*SOLD OUT\s*$", "", title).strip()
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        dl = next((l for l in lines if re.search(r"\b(until|from|\d{1,2}\s+[A-Z][a-z]{2})\b", l) and "in **" in l or re.match(r"(?:Until|From)\s", l) or re.match(r"\d{1,2}\s+[A-Z][a-z]{2}", l)), "")
        if not dl:
            continue
        place = _place(dl)
        venue = "Amsterdam Museum" + (f" · {place}" if place and place != "Amsterdam Museum" else "")
        blurb = lines[0] if lines and lines[0] != dl else ""
        dates = find_dates(dl.split(" in **")[0], today)
        if not dates:
            continue
        if kind == "exhibition":
            if re.match(r"\s*From", dl, re.I):
                start, end = dates[0], None
                if start > today + timedelta(days=240):
                    continue
                sp = (start, None)
            else:
                sp = span(None, dates[-1], today)
            if not sp or (title, sp[0]) in seen:
                continue
            seen.add((title, sp[0]))
            e = {"t": title, "d": sp[0].isoformat(), "c": "exhibition"}
            if sp[1]:
                e["ed"] = sp[1].isoformat()
            out.append(dict(e, v=venue, u=url, s="amsterdammuseum", **({"b": blurb[:160]} if blurb else {})))
        else:
            if re.match(r"\s*Until", dl, re.I):
                continue   # runs of a children's camp etc.: no single date to show
            for d in dates:
                if d < today or d > today + timedelta(days=240) or (title, d) in seen:
                    continue
                seen.add((title, d))
                cat = "kids" if re.search(r"\(age|kids|kinder", title, re.I) else ("workshop" if re.search(r"workshop", title, re.I) else "other")
                e = {"t": title, "d": d.isoformat(), "c": cat, "v": venue, "u": url, "s": "amsterdammuseum"}
                if blurb:
                    e["b"] = blurb[:160]
                out.append(e)
    return out
