"""City of Amsterdam activities calendar (activiteiten.amsterdam.nl).

Public listing of neighbourhood sessions, drop-ins, info evenings and the council and district meetings. The pager
overlaps (later pages repeat earlier ones), so every page is read and entries are de-duplicated by id. Date ranges
longer than a few days are recurring series with no single date and are skipped.

Labels (field "lb"), shown on the event and searchable but not a filter:
  Politics       council committees (merged per day into one event) and district commissions. Always shown.
  Support        weekly drop-ins, walking groups, health talks. Quiet: "q": 1
  Neighbourhood  everything else (info evenings, workshops, kids). Quiet: "q": 1
Quiet events only show under the Community chip or in search (see passes() in template.html).
Left out on purpose: Weesp board meetings and the district board drop-in hours.
"""
import datetime, html, json, re, subprocess

BASE = "https://activiteiten.amsterdam.nl/?pager_page="
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
PAGES = 21
HORIZON_DAYS = 120
MON = {"januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7, "augustus": 8,
       "september": 9, "oktober": 10, "november": 11, "december": 12}

SKIP = re.compile(r"weesp|\bAB[ -]vergadering|inloopspreekuur|dagelijks bestuur\b(?!.*stadsdeelcommissie)", re.I)
COUNCIL = re.compile(r"^gemeenteraad:?\s*commissievergadering\s*", re.I)
DISTRICT = re.compile(r"stadsdeelcommissie|stadsgebied", re.I)
SUPPORT = re.compile(
    r"inloop|open huiskamer|buurtkamer|respijt|moedergroep|dementie|ontbijt|wandel|beweeg|theetuin|senioren|mantelzorg|"
    r"\bzorg|spreekuur|koffie|ontmoet|lunch|eetpunt|samen eten|maaltijd|huiswerk|leren lezen|adhd|mentale|gezondheid|voorlichting", re.I)


def fetch(out):
    pages = []
    for p in range(PAGES):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, BASE + str(p)], capture_output=True, text=True)
        if r.returncode != 0 or "resultaat" not in r.stdout: break
        pages.append(r.stdout)
    if not pages: raise RuntimeError("no pages")
    with open(out, "w") as f: json.dump(pages, f)
    return len(pages)


def _entries(pages):
    seen = {}
    for t in pages:
        for m in re.finditer(r'<div class=resultaat id=result_(\d+)>(.*?)(?=<div class=resultaat id=result_|<div class="pager)', t, re.S):
            if m.group(1) in seen: continue
            b = m.group(2)
            a = re.search(r'<h2 class=link><a href="([^"]+)">(.*?)</a>', b, re.S)
            d = re.search(r'class="datum meta">(.*?)</div>', b, re.S)
            if not a or not d: continue
            loc = re.search(r'locatie">(.*?)</div>', b, re.S)
            txt = re.search(r"<p class=tekst>(.*?)</p>", b, re.S)
            clean = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
            seen[m.group(1)] = dict(u=a.group(1), t=clean(a.group(2)), date=clean(d.group(1)),
                                    v=clean(loc.group(1)) if loc else "", b=clean(txt.group(1)) if txt else "")
    return list(seen.values())


def _when(s):
    days = [datetime.date(int(y), MON[m], int(d)) for d, m, y in re.findall(r"(\d{1,2}) ([a-z]+) (\d{4})", s) if m in MON]
    if not days or (days[-1] - days[0]).days > 3: return None, "", ""
    times = re.findall(r"(\d{1,2})[.:](\d{2})", s)
    h = f"{int(times[0][0]):02d}:{times[0][1]}" if times else ""
    eh = f"{int(times[1][0]):02d}:{times[1][1]}" if len(times) > 1 else ""
    return days[0], h, eh


def parse(text, today):
    horizon = today + datetime.timedelta(days=HORIZON_DAYS)
    out, council, seen = [], {}, set()
    for it in _entries(json.loads(text)):
        d, h, eh = _when(it["date"])
        if not d or d < today or d > horizon: continue
        if SKIP.search(it["t"]) or SKIP.search(it["v"]): continue
        key = (d, it["t"].lower())
        if key in seen: continue
        seen.add(key)
        base = {"d": d.isoformat(), "h": h, "eh": eh, "v": it["v"], "u": it["u"], "c": "community", "s": "amsterdamcal", "nl": 1}
        if it["b"]: base["b"] = it["b"][:220]
        if COUNCIL.search(it["t"]):
            council.setdefault(d, []).append((h, eh, COUNCIL.sub("", it["t"]), it["u"]))
        elif DISTRICT.search(it["t"]) or re.search(r"commissie", it["t"], re.I):
            out.append({**base, "t": it["t"], "lb": "Politics"})
        else:
            out.append({**base, "t": it["t"], "lb": "Support" if SUPPORT.search(it["t"] + " " + it["v"]) else "Neighbourhood", "q": 1})
    for d, items in council.items():                # one event per day for all council committees
        items.sort()
        names = ", ".join(n for _, _, n, _ in items)
        starts = [h for h, _, _, _ in items if h]
        ends = [e for _, e, _, _ in items if e]
        e = {"t": ("Gemeenteraad commissies: " if len(items) > 1 else "Gemeenteraad commissie: ") + names, "d": d.isoformat(),
             "v": "Stadhuis, Amsterdam", "u": items[0][3], "c": "community", "s": "amsterdamcal", "nl": 1, "lb": "Politics"}
        if starts: e["h"] = starts[0]
        if ends: e["eh"] = max(ends)
        if len(items) > 1: e["b"] = " · ".join(f"{h or '?'} {n}" for h, _, n, _ in items)
        else: e["b"] = "Open to the public. Usually also streamed online."
        out.append(e)
    return out
