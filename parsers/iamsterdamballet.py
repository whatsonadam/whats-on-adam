"""Dutch National Ballet nights from I amsterdam event pages.
The Uitagenda listing only gives a run ("t/m 24 apr"), but every event page carries the full
per-night list (eventDates) in its page data. find_links() picks ballet pages out of the
listing pages; parse_pages() reads the night lists. Opera is covered by theater.nl."""
import datetime, json, re
HORIZON = 240
VENUE = "Nationale Opera & Ballet"

def find_links(pages):
    """Hrefs of ballet productions at the Nationale Opera & Ballet, from listing pages."""
    import iamsterdam
    out = []
    for html in pages:
        for href, p, t in iamsterdam.cards(html):
            tags = {x.strip() for x in t.split(",")}
            if "Locatie" in p and VENUE in p[p.index("Locatie") + 1] and "ballet" in tags and href not in out:
                out.append(href)
    return out

def _json_after(html, key):
    m = re.search(r'\\"%s\\":(\[)' % key, html)
    if not m: return None
    s = html[m.start(1):]
    s = s.replace('\\"', '"')
    depth = 0
    for i, ch in enumerate(s):
        if ch == "[": depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try: return json.loads(s[:i + 1])
                except ValueError: return None
    return None

def parse_pages(pages, today):
    """pages: {href: html}. One event per night."""
    out = []; end = today + datetime.timedelta(days=HORIZON)
    for href, html in pages.items():
        dates = _json_after(html, "eventDates")
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
        if not dates or not title:
            print(f"  iamsterdamballet: no dates or title on {href}")
            continue
        pm = re.search(r'\\"rateFrom\\":(\d+(?:\.\d+)?)', html)
        desc = re.search(r'"description":"([^"]*)"', html)
        sold = bool(desc and re.search(r"sold out|uitverkocht", desc.group(1), re.I))
        for dd in dates:
            try:
                a = datetime.datetime.fromisoformat(dd["from"][:19]); b = datetime.datetime.fromisoformat(dd["until"][:19])
            except (KeyError, ValueError): continue
            if not (today <= a.date() <= end): continue
            e = {"t": title, "d": a.date().isoformat(), "h": a.strftime("%H:%M"), "v": VENUE, "addr": "Amstel 3",
                 "u": "https://www.iamsterdam.com" + href, "c": "dance", "s": "iamsterdam"}
            if b > a: e["eh"] = b.strftime("%H:%M")
            if pm: e["p"] = "from €%s" % pm.group(1)
            if sold: e["b"] = "Some nights are sold out, check the venue for tickets"
            out.append(e)
    return out
