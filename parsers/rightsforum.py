"""The Rights Forum agenda (rightsforum.org/agenda): vigils, marches and actions for Palestine across the Netherlands.

Server-rendered WordPress pages (/agenda/, /agenda/page/N/), 15 cards each. A card has a heading
"<date> / <title>" and a list with Wat, Waar, Wanneer, Tijd and Door. The agenda is national, so only cards whose
location (Waar, or the title when there is none) says Amsterdam are kept. Recurring actions are listed once per day
by the source; the build merges identical ones. Everything is Dutch, so events are marked tl=1 for translation.
"""
import datetime, os, re, subprocess, time
from bs4 import BeautifulSoup

try:
    from _dates import MONTHS, make_date
except ImportError:  # pragma: no cover
    from parsers._dates import MONTHS, make_date

BASE = "https://rightsforum.org/agenda/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 15
AMS = re.compile(r"\bamsterdam\b", re.I)
DATE = re.compile(r"(\d{1,2})\s+([a-z]+)\s+(20\d\d)", re.I)
TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "45", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def fetch(dirpath):
    """Download every agenda page into dirpath/pNN.html, politely. Returns the number of pages."""
    os.makedirs(dirpath, exist_ok=True)
    for f in os.listdir(dirpath):
        os.remove(os.path.join(dirpath, f))
    n = 0
    for p in range(1, MAX_PAGES + 1):
        out = os.path.join(dirpath, f"p{p:02d}.html")
        code = _curl(BASE if p == 1 else f"{BASE}page/{p}/", out)
        if code != "200":
            if os.path.exists(out): os.remove(out)
            if p == 1: raise RuntimeError(f"agenda returned {code}")
            break
        if "agenda__item" not in open(out, errors="ignore").read():
            os.remove(out); break
        n += 1
        time.sleep(1.0)
    return n


def _fields(article):
    d = {}
    for li in article.select("ul > li"):
        lab = li.find("strong")
        if lab:
            name = lab.get_text(strip=True).rstrip(":").lower()
            lab.extract()
            d[name] = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
    return d


def parse_pages(pages, today):
    out, seen = [], set()
    for html in pages:
        for art in BeautifulSoup(html, "html.parser").select("article.agenda__item"):
            h3 = art.find("h3")
            if not h3: continue
            span = h3.find("span")
            m = DATE.search(span.get_text(" ", strip=True) if span else "")
            if not m or m.group(2).lower() not in MONTHS: continue
            d = make_date(int(m.group(1)), MONTHS[m.group(2).lower()], m.group(3), today)
            if not d or d < today: continue
            if span: span.extract()
            title = re.sub(r"\s+", " ", h3.get_text(" ", strip=True)).strip()
            f = _fields(art)
            where = f.get("waar", "")
            if not AMS.search(where or title): continue
            more = art.select_one("a.agenda__meer")
            link = (more.get("href") if more else None) or BASE
            key = (d, title.lower(), link)
            if key in seen: continue
            seen.add(key)
            e = {"t": title, "d": d.isoformat(), "v": where or "Amsterdam", "u": link, "c": "protest", "s": "rightsforum", "tl": 1}
            times = TIME.findall(f.get("tijd", ""))
            if times:
                e["h"] = f"{int(times[0][0]):02d}:{times[0][1]}"
                if len(times) > 1: e["eh"] = f"{int(times[1][0]):02d}:{times[1][1]}"
            blurb = f.get("wat", "")
            if f.get("door"): blurb = (blurb + " " if blurb else "") + f"Georganiseerd door {f['door']}."
            if blurb: e["b"] = blurb
            out.append(e)
    return out
