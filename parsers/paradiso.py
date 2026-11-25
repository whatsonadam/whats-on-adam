"""Paradiso (paradiso.nl/en/program): concerts and club nights at Paradiso and the halls it programmes elsewhere.

The program page is server-rendered with the next few days of events embedded as Next.js data ("eventType" objects with
startDateTime in local time, subtitle, location and a soldOut flag). Later events load in the browser only, so this
reader covers the coming days and the I amsterdam agenda stays the backup for the weeks after. Each event's own page
gives the ticket price ("Ticket € 45,40", plus a note when a membership is needed); those pages are fetched once
(one per second). Highlight blocks on the page use another time format and are ignored.
"""
import datetime, json, os, re, subprocess, time
from html import unescape

try:
    from _price import clean as clean_price
except ImportError:
    from parsers._price import clean as clean_price

BASE = "https://www.paradiso.nl"
LIST = BASE + "/en/program"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
CLUB = re.compile(r"club ?night|clubnacht|\bdj\b|\bparty\b|rave", re.I)


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-L", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def _payload(html):
    parts = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    out = []
    for p in parts:
        try: out.append(json.loads('"' + p + '"'))
        except ValueError: pass
    return "".join(out)


def _events(html):
    s, dec, out = _payload(html), json.JSONDecoder(), {}
    for m in re.finditer(r'\{"__typename":"eventType"', s):
        try: o, _ = dec.raw_decode(s[m.start():])
        except ValueError: continue
        if o.get("id") and o.get("startDateTime") and o.get("title"): out[o["id"]] = o
    return list(out.values())


def fetch(dirpath):
    os.makedirs(os.path.join(dirpath, "detail"), exist_ok=True)
    path = os.path.join(dirpath, "list.html")
    if _curl(LIST, path) != "200": raise RuntimeError("paradiso program not reachable")
    evs = _events(open(path, errors="ignore").read())
    if not evs: raise RuntimeError("paradiso: no events in page (layout change?)")
    for o in evs:
        _curl(BASE + "/en/" + o["uri"], os.path.join(dirpath, "detail", o["id"] + ".html"))
        time.sleep(1)
    return len(evs)


def _detail(html):
    x = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S)
    x = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", x)))
    price = None
    m = re.search(r"Ticket\s*€\s*(\d+(?:[.,]\d+)?)", x)
    if m:
        price = clean_price(m.group(1))
        if price and re.search(r"Excluding € ?[\d,]+ monthly membership", x): price += " + membership"
    elif re.search(r"\bFree\b(?! service)", x[:3000]) and "Ticket" in x[:3000]:
        price = "Free"
    room = None
    m = re.search(r"In Paradiso - ([A-Z][\w ]+?) (?:Doors|Start)", x)
    if m: room = m.group(1).strip()
    return price, room


def parse_pages(list_html, details, today):
    out = []
    for o in _events(list_html):
        try: st = datetime.datetime.fromisoformat(o["startDateTime"])
        except ValueError: continue
        if st.date() < today or o.get("eventStatus") in ("canceled", "cancelled", "postponed"): continue
        loc = (o.get("location") or {}).get("title") or "Paradiso"
        title = re.sub(r"\s+", " ", o["title"]).strip()
        sub = o.get("subtitle") or ""
        e = {"t": title, "d": st.date().isoformat(), "h": st.strftime("%H:%M"),
             "v": loc,
             "u": BASE + "/en/" + o["uri"], "c": "club" if CLUB.search(sub + " " + title) else "music", "s": "paradiso"}
        price, room = _detail(details[o["id"]]) if o["id"] in details else (None, None)
        if e["v"] == "Paradiso" and room: e["v"] = "Paradiso · " + room
        if o.get("soldOut") == "yes": e["so"] = 1
        if price: e["p"] = price
        sub = re.sub(r"\s*/\s*[^/]+$", "", sub) if "/" in sub else sub
        if sub: e["b"] = sub[:220]
        out.append(e)
    return out


def load(dirpath):
    lp = os.path.join(dirpath, "list.html")
    lh = open(lp, errors="ignore").read() if os.path.exists(lp) else ""
    dd = os.path.join(dirpath, "detail")
    det = {f[:-5]: open(os.path.join(dd, f), errors="ignore").read() for f in os.listdir(dd) if f.endswith(".html")} if os.path.isdir(dd) else {}
    return lh, det
