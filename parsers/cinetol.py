"""Cinetol parser. Input: the page's raw HTML (fetch.py saves it as cinetol.html).
Each programme card is a .cms_list-item with the date (dd.mm), a hidden year tag, the
act name (h2), genres and a /events/<slug> link."""
import datetime, re
from bs4 import BeautifulSoup
SRC = "https://www.cinetol.nl/programma"
def parse(text, today):
    if "<" not in text: return []
    s = BeautifulSoup(text, "html.parser")
    out = []
    for it in s.select(".cms_list-item"):
        h2 = it.select_one("h2")
        loc = it.select_one(".card_location .event_date-flex")
        if not h2 or not loc: continue
        nums = [x.get_text(strip=True) for x in loc.find_all("div")]
        nums = [n for n in nums if n.isdigit()]
        if len(nums) < 2: continue
        day, mon = int(nums[0]), int(nums[1])
        yr = None
        for tag in it.select(".event-tag.filter"):
            t = tag.get_text(strip=True)
            if re.fullmatch(r"20\d\d", t): yr = int(t)
        if not yr:
            yr = today.year + (1 if mon < today.month - 2 else 0)
        try: d = datetime.date(yr, mon, day)
        except ValueError: continue
        if d < today or d > today + datetime.timedelta(days=120): continue
        title = h2.get_text(" ", strip=True)
        sup = it.select_one("h3")
        sup = sup.get_text(" ", strip=True) if sup else ""
        genres = [g.get_text(strip=True) for g in it.select('[fs-list-field="genre"]')]
        a = it.select_one('a[href^="/events/"]')
        e = {"t": title, "d": d.isoformat(), "v": "Cinetol", "s": "cinetol",
             "u": ("https://www.cinetol.nl" + a["href"]) if a else SRC, "c": "music"}
        gl = " ".join(genres).lower() + " " + title.lower()
        if any(k in gl for k in ["film", "screening"]): e["c"] = "film"
        elif any(k in gl for k in ["talk", "lezing", "gesprek"]): e["c"] = "talk"
        elif any(k in gl for k in ["club", "dj", "techno", "house"]): e["c"] = "club"
        b = ", ".join(x for x in [sup, " / ".join(genres)] if x)
        if b: e["b"] = b[:120]
        if it.select_one(".sold-out"): e["p"] = "Sold out"
        out.append(e)
    return out
