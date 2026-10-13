"""Rialto parser (venues Rialto De Pijp and Rialto VU Griffioen).
Input: text with one JSON document per line (NDJSON), written by a curl step:
  * De Pijp: POST https://depijp.rialtofilm.nl/prod/nl/api/events/byday (pageSize<=100, page 1..pages)
    -> {"events":[{"day","event":{title,url,programs:[{id,startAt,isCanceled,button}]}}],"pagination":{...}}
  * VU Griffioen: GET https://griffioen.vu.nl/shows.php?genres=&dates=&type=film&page=N
    -> {"html": "<div class='program-item' onclick=\"document.location='/film/<slug>/dd-mm-yyyy-HH-MM'\">...<strong>Title</strong>", "pages": N}
Lines are told apart by their keys ('events' = De Pijp, 'html' = Griffioen)."""
import datetime, html as htmlmod, json, re

PIJP = "https://depijp.rialtofilm.nl"
GRIF = "https://griffioen.vu.nl"
ITEM_RE = re.compile(
    r"document\.location='(/film/[^']*?/(\d\d)-(\d\d)-(\d{4})-(\d\d)-(\d\d))'.*?<strong>(.*?)</strong>", re.S)


def _add(out, seen, e, today, end):
    try:
        d = datetime.date.fromisoformat(e["d"])
    except ValueError:
        return
    if not e["t"] or not (today <= d <= end):
        return
    if e.get("h") and e["h"] < "06:00":  # 00:00 / 01:00 placeholders for unscheduled slots
        del e["h"]
    k = (e["v"], e["t"], e["d"], e.get("h"))
    if k in seen:
        return
    seen.add(k)
    out.append(e)


def parse(text, today):
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        for x in doc.get("events") or []:
            ev = x.get("event") or {}
            title = (ev.get("title") or "").strip()
            for p in ev.get("programs") or []:
                if p.get("isCanceled") or not p.get("startAt"):
                    continue
                d, _, hm = p["startAt"].partition("T")
                e = {"t": title, "d": d, "v": "Rialto De Pijp", "c": "film", "s": "rialto",
                     "u": PIJP + ev["url"] if ev.get("url") else PIJP + "/nl/agenda"}
                if hm[:5]:
                    e["h"] = hm[:5]
                _add(out, seen, e, today, end)
        if doc.get("html"):
            for m in ITEM_RE.finditer(doc["html"]):
                path, dd, mm, yy, hh, mi, title = m.groups()
                title = htmlmod.unescape(re.sub(r"<[^>]+>", "", title)).strip()
                e = {"t": title, "d": f"{yy}-{mm}-{dd}", "h": f"{hh}:{mi}", "v": "Rialto VU Griffioen",
                     "c": "film", "s": "rialto", "u": GRIF + path}
                _add(out, seen, e, today, end)
    return out


def fetch_text(today, out_path, ua="Mozilla/5.0"):
    """curl step (one request per second): writes the NDJSON that parse() reads.
    De Pijp: POST byday pages (<=100 per page, programme is published ~2-3 weeks ahead);
    Griffioen: GET shows.php pages (all published shows, 2 pages)."""
    import subprocess, time
    end = today + datetime.timedelta(days=120)
    lines = []
    page = 1
    while page <= 20:
        body = {"filters": {"genre": {"includes": [], "excludes": []}, "eventAttribute": {"includes": [], "excludes": []},
                            "programAttribute": {"includes": [], "excludes": [7]},
                            "location": {"includes": [], "excludes": []}, "event": {"includes": [], "excludes": []},
                            "startAt": f"{today}T00:00:00.000Z", "endAt": f"{end}T23:59:59.999Z", "searchTerm": ""},
                "pagination": {"page": page, "pageSize": 100}, "sortings": []}
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", ua, "-H", "content-type: application/json",
                            "--data", json.dumps(body), PIJP + "/prod/nl/api/events/byday"],
                           capture_output=True, text=True).stdout
        d = json.loads(r)
        lines.append(json.dumps(d))
        if page >= d["pagination"]["pages"]:
            break
        page += 1
        time.sleep(1)
    page = 1
    while page <= 20:
        time.sleep(1)
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", ua,
                            f"{GRIF}/shows.php?genres=&dates=&type=film&page={page}"],
                           capture_output=True, text=True).stdout
        d = json.loads(r)
        lines.append(json.dumps(d))
        if page >= d.get("pages", 1):
            break
        page += 1
    open(out_path, "w").write("\n".join(lines) + "\n")
