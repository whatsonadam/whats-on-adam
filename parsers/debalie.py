"""De Balie (debalie.nl): debates, lectures and talks on politics, culture and society.

The site's own programme list loads from its public WordPress API (post type vo-programme), which gives date, start
time and link for every upcoming item, so no browser is needed. Closed events ("besloten") and items hosted elsewhere
(no start time, link to another ticket shop) are skipped. De Balie's cinema programme is not read here.
"""
import datetime, html, json, re, subprocess

API = "https://debalie.nl/wp-json/wp/v2/vo-programme?per_page=100&orderby=date&page="
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
MAX_PAGES = 5


def fetch(out):
    items = []
    for p in range(1, MAX_PAGES + 1):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", UA, API + str(p)], capture_output=True, text=True)
        try: d = json.loads(r.stdout)
        except Exception: break
        if not isinstance(d, list) or not d: break
        items += d
        if len(d) < 100: break
    if not items: raise RuntimeError("no items")
    with open(out, "w") as f: json.dump(items, f)
    return len(items)


def parse(text, today):
    out, seen = [], set()
    for it in json.loads(text):
        v = it.get("vo") or {}
        raw = v.get("date_raw") or ""
        time_raw = (v.get("time_raw") or v.get("time") or "").strip()
        try: d = datetime.date.fromisoformat(raw[:10])
        except ValueError: continue
        if d < today or it.get("id") in seen: continue
        seen.add(it.get("id"))
        ext = v.get("external_link") or {}
        if re.search(r"besloten|closed", (ext.get("text") or ""), re.I): continue
        if not re.match(r"^\d{1,2}:\d{2}$", time_raw): continue        # no start time: closed or hosted elsewhere
        title = re.sub(r"\s+", " ", html.unescape((it.get("title") or {}).get("rendered") or "")).strip()
        if not title: continue
        e = {"t": title, "d": d.isoformat(), "h": time_raw.zfill(5), "v": "De Balie", "u": it.get("link"), "c": "talk", "s": "debalie"}
        sub = html.unescape((v.get("subtitle") or "").strip())
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", v.get("short_description") or v.get("description") or ""))).strip()
        b = (sub + ". " if sub else "") + desc
        if b.strip(". "): e["b"] = b[:300]
        out.append(e)
    return out
