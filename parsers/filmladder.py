"""The big cinema chains in Amsterdam (Pathé Tuschinski, City, De Munt, Arena, Noord and Vue), read from
Filmladder.nl's Amsterdam cinema overview (https://www.filmladder.nl/amsterdam/bioscopen). The chains' own sites
block automated readers. Filmladder lists the coming 7 days with each screening's start time. Only the chains are
taken from the page; the other cinemas have their own, better sources. Events carry ch=1 so the site can hide them
by default."""
import datetime, html as _html, re

CHAIN = re.compile(r"path[eé]|\bvue\b", re.I)
CINEMA = re.compile(r'<div class="cinema">(.*?)(?=<div class="cinema">|\Z)', re.S)
NAME = re.compile(r'class="cinema-link"[^>]*>([^<]+)<')
HALL = re.compile(r'<div class="hall [^"]*">(.*?)(?=<div class="hall |\Z)', re.S)
TITLE = re.compile(r'<h4>\s*<a [^>]*class="movie-link text-link"[^>]*>(.*?)(?:<span|</a>)', re.S)
SHOW = re.compile(r'itemprop="startDate" content="(\d{4}-\d\d-\d\dT\d\d:\d\d)[^"]*"(?:[^>]*title="van (\d\d:\d\d) tot (\d\d:\d\d)")?[^>]*>(.*?)</div>', re.S)
HREF = re.compile(r'href="([^"]+)"')


def parse(text, today):
    out = []
    end = today + datetime.timedelta(days=14)
    for block in CINEMA.findall(text):
        m = NAME.search(block)
        if not m: continue
        venue = _html.unescape(m.group(1)).strip()
        if not CHAIN.search(venue): continue
        for hall in HALL.findall(block):
            tm = TITLE.search(hall)
            title = _html.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip() if tm else ""
            if not title: continue
            for iso, s, e, inner in SHOW.findall(hall):
                d = datetime.date.fromisoformat(iso[:10])
                if not (today <= d <= end): continue
                href = HREF.search(inner)
                ev = {"t": title, "d": d.isoformat(), "h": iso[11:16], "v": venue,
                      "u": href.group(1) if href else "https://www.filmladder.nl/amsterdam/bioscopen",
                      "c": "film", "s": "filmladder", "ch": 1}
                if s and e:
                    a = int(s[:2]) * 60 + int(s[3:]); b = int(e[:2]) * 60 + int(e[3:])
                    if b < a: b += 1440
                    if 30 <= b - a <= 330: ev["du"] = b - a
                out.append(ev)
    return out
