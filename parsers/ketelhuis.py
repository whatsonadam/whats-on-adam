"""Het Ketelhuis parser (site: www.ketelhuis.nl; note hetketelhuis.nl is a domain-for-sale page).
The agenda loads one day at a time via POST https://www.ketelhuis.nl/wp-admin/admin-ajax.php
(action=agenda_filter_call&a_type=agenda&a_date=YYYY-MM-DD&a_filter=) -> {"success":true,"data":"<html>"}.
fetch(path, today) does the polite loop (1 request/second) and writes [{"date","html"}, ...] to path."""
import datetime, json, subprocess, time
from bs4 import BeautifulSoup

URL = "https://www.ketelhuis.nl/wp-admin/admin-ajax.php"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
DAYS = 60  # programme is published ~3-4 weeks ahead with gaps; 60 days is cheap

def fetch(path, today, days=DAYS):
    out = []
    for i in range(days):
        d = (today + datetime.timedelta(days=i)).isoformat()
        r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, "-X", "POST", URL, "-d", "action=agenda_filter_call",
                            "-d", "a_type=agenda", "-d", "a_date=" + d, "-d", "a_filter="], capture_output=True, text=True)
        try: j = json.loads(r.stdout)
        except ValueError: j = None
        if j and j.get("success") and j.get("data") not in (None, "", "0"): out.append({"date": d, "html": j["data"]})
        time.sleep(1.0)
    json.dump(out, open(path, "w"))
    return len(out)

def parse(text, today):
    try: days = json.loads(text)
    except ValueError: return []
    if not isinstance(days, list): return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for day in days:
        if not isinstance(day, dict): continue
        s = BeautifulSoup(day.get("html") or "", "html.parser")
        for it in s.select(".c-schedule-list__item"):
            a = it.select_one("h2 a")
            title = (a.get_text(" ", strip=True) if a else it.get("data-item-title") or "").strip()
            if not title: continue
            url = a["href"] if a and a.get("href") else "https://www.ketelhuis.nl/agenda/"
            for tm in it.select("time[datetime]"):
                dt = tm["datetime"].strip()
                try: when = datetime.datetime.strptime(dt[:16], "%Y-%m-%d %H:%M")
                except ValueError: continue
                d = when.date()
                if d < today or d > end: continue
                h = when.strftime("%H:%M")
                k = (title, d, h)
                if k in seen: continue
                seen.add(k)
                out.append({"t": title, "d": d.isoformat(), "h": h, "v": "Het Ketelhuis", "u": url, "c": "film", "s": "ketelhuis"})
    out.sort(key=lambda e: (e["d"], e["h"]))
    return out
