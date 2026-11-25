"""QueerHub Amsterdam / Pink Nieuw-West (pinknieuwwest.org): queer and community nights in Nieuw-West.

The site is WordPress with The Events Calendar and publishes an iCal feed. The feed labels times as UTC but they are the
local Amsterdam clock times (they match the page), so they are used as written. Entries are bilingual (Dutch, then
English), so they are not flagged Dutch-only. "Kosten: ... gratis" in the text means free.
"""
import datetime, re, subprocess

FEED = "https://www.pinknieuwwest.org/activiteiten/?ical=1"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def fetch(out):
    r = subprocess.run(["curl", "-sS", "-m", "60", "-L", "-A", UA, "-o", out, "-w", "%{http_code}", FEED], capture_output=True, text=True)
    if r.stdout.strip() != "200": raise RuntimeError("http " + r.stdout.strip())
    n = open(out, errors="ignore").read().count("BEGIN:VEVENT")
    if not n: raise RuntimeError("no events")
    return n


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text)


def _val(block, key):
    m = re.search(r"^" + key + r"(?:;[^:\n]*)?:(.*)$", block, re.M)
    return re.sub(r"\\([,;nN\\])", lambda x: "\n" if x.group(1) in "nN" else x.group(1), m.group(1)).strip() if m else ""


def _dt(s):
    m = re.search(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})", s)
    return (datetime.date(int(m[1]), int(m[2]), int(m[3])), f"{m[4]}:{m[5]}") if m else (None, "")


def parse(text, today):
    out = []
    for block in _unfold(text).split("BEGIN:VEVENT")[1:]:
        d, h = _dt(_val(block, "DTSTART"))
        if not d or d < today: continue
        _, eh = _dt(_val(block, "DTEND"))
        title = re.sub(r"\s+[-–—]\s+\d{1,2} (?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s*$", "", _val(block, "SUMMARY"), flags=re.I).strip()
        if not title: continue
        title = title.replace("​", "").strip()
        desc = _val(block, "DESCRIPTION").replace("​", "")
        loc = _val(block, "LOCATION")
        parts = [x.strip() for x in loc.split(",") if x.strip()]
        e = {"t": title, "d": d.isoformat(), "u": _val(block, "URL"), "c": "community", "s": "pinknieuwwest", "v": parts[0] if parts else "QueerHub"}
        if len(parts) > 1 and re.search(r"\d", parts[1]): e["addr"] = parts[1] + ", Amsterdam"
        if h and h != "00:00": e["h"] = h
        if eh and eh != "00:00" and eh != h: e["eh"] = eh
        if re.search(r"kosten:\s*(?:deelname is )?gratis|cost:\s*(?:participation is )?free", desc, re.I): e["p"] = "Free"
        body = re.split(r"\s*(?:Wanneer|When):", desc)[0]
        body = re.sub(r"\s+", " ", body).strip()
        if body: e["b"] = body[:220]
        out.append(e)
    return out
