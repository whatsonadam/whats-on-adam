"""socialisme.nu agenda (socialisme.nu/agenda/): demonstrations, actions and meetings from the Internationale Socialisten.

One server-rendered page with schema.org Event markup (startDate, location, name, description, url). The agenda is
national, so only entries whose place is Amsterdam are kept. A start time of 00:00 means no time was given. Dutch and
English text is marked tl=1 for translation. Entries are shown as protest and activism.
"""
import datetime, re, subprocess
from bs4 import BeautifulSoup

URL = "https://socialisme.nu/agenda/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
AMS = re.compile(r"\bamsterdam\b", re.I)


def fetch(out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", URL], capture_output=True, text=True)
    return r.stdout.strip()


def parse(text, today):
    out, seen = [], set()
    for li in BeautifulSoup(text, "html.parser").select("li[itemtype$='Event']"):
        tm, name, url = li.find(attrs={"itemprop": "startDate"}), li.find(attrs={"itemprop": "name"}), li.find(attrs={"itemprop": "url"})
        loc = li.find(attrs={"itemprop": "addressLocality"})
        if not (tm and name and url) or not loc or not AMS.search(loc.get("content", "")): continue
        m = re.search(r"(20\d\d)\D+(\d\d)-(\d\d)T(\d\d):(\d\d)", tm.get("datetime", "") or tm.get("dateTime", "") or tm.get_text())
        if not m: continue
        try: d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: continue
        link = url.get("href")
        if d < today or link in seen: continue
        seen.add(link)
        e = {"t": re.sub(r"\s+", " ", name.get_text(" ", strip=True)), "d": d.isoformat(), "v": "Amsterdam", "u": link,
             "c": "protest", "s": "socialisme", "tl": 1}
        if (m.group(4), m.group(5)) != ("00", "00"): e["h"] = f"{m.group(4)}:{m.group(5)}"
        desc = li.find(attrs={"itemprop": "description"})
        b = re.sub(r"\s+", " ", desc.get_text(" ", strip=True)).strip() if desc else ""
        if b: e["b"] = b
        out.append(e)
    return out
