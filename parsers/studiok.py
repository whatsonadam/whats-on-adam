"""Studio/K parser. The film calendar on studio-k.nu loads one day at a time via
POST https://studio-k.nu/wp-admin/admin-ajax.php (action=loadShows&date=YYYY-MM-DD) -> {"max","size","day","html"}.
fetch(path, today) below does the polite loop (1 request/second) and writes a JSON list
[{"date": "YYYY-MM-DD", "html": "<ul>...</ul>"}, ...] to path; parse() reads that file's text."""
import datetime, html as _html, json, re, subprocess, time

URL = "https://studio-k.nu/wp-admin/admin-ajax.php"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
DAYS = 60  # the site only lists ~3 weeks plus a few later specials; 60 days is cheap

def fetch(path, today, days=DAYS):
    out = []
    for i in range(days):
        d = (today + datetime.timedelta(days=i)).isoformat()
        r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, "-X", "POST", URL,
                            "-d", "action=loadShows", "-d", "date=" + d], capture_output=True, text=True)
        try: j = json.loads(r.stdout)
        except ValueError: j = None
        if j and j.get("html"): out.append({"date": d, "html": j["html"]})
        time.sleep(1.0)
    json.dump(out, open(path, "w"))
    return len(out)

ITEM = re.compile(r'<li><a href="([^"]+)" class="title">(.*?)</a><a href="[^"]*" class="time">(\d{1,2}:\d\d)</a>', re.S)

def parse(text, today):
    try: days = json.loads(text)
    except ValueError: return []
    if not isinstance(days, list): return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for day in days:
        try: d = datetime.date.fromisoformat(day.get("date", ""))
        except (ValueError, AttributeError): continue
        if d < today or d > end: continue
        for url, title, hh in ITEM.findall(day.get("html") or ""):
            title = _html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
            if not title: continue
            h = hh.zfill(5)
            k = (title, d, h)
            if k in seen: continue
            seen.add(k)
            out.append({"t": title, "d": d.isoformat(), "h": h, "v": "Studio/K", "u": _html.unescape(url).split("#")[0],
                        "c": "film", "s": "studiok"})
    return out
