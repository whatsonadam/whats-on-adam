"""DeLaMar Theater: every show page from the Dutch site (delamar.nl/voorstellingen/<show>/).

fetch() reads the sitemap, downloads each show page into _data/delamar/ (a few at a time, politely) and
parse_pages() turns them into one event per performance. Each performance has its own date, start time,
'from' price and a sold-out flag. DeLaMar prices are consumer ticket prices, so they include VAT.
"""
import concurrent.futures as cf, datetime, html, os, re, subprocess, time

BASE = "https://delamar.nl"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
GENRE_CAT = {"cabaret": "comedy", "concert": "music", "dans": "dance", "jeugd": "kids"}
DATE_RX = re.compile(r'<div class="production__date js-production-date[^"]*" data-date="(\d{4}-\d\d-\d\d)">(.*?)</div>\s*'
                     r'(?:<span class="button([^"]*)">\s*(.*?)\s*</span>|<a[^>]*class="button([^"]*)"[^>]*>\s*(.*?)\s*</a>)', re.S)


def _curl(url, out):
    r = subprocess.run(["curl", "-sS", "-m", "30", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()


def fetch(out_dir, workers=4):
    """Download all show pages. Returns how many were saved. Raises if the sitemap cannot be read."""
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir): os.remove(os.path.join(out_dir, f))
    sm = os.path.join(out_dir, "_sitemap.xml")
    if _curl(BASE + "/sitemap.xml", sm) != "200": raise RuntimeError("DeLaMar sitemap not readable")
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", open(sm, errors="ignore").read())
            if "/voorstellingen/" in u and not u.rstrip("/").endswith("/voorstellingen")]
    os.remove(sm)
    if not urls: raise RuntimeError("DeLaMar sitemap had no shows")

    def get(u):
        out = os.path.join(out_dir, u.rstrip("/").rsplit("/", 1)[1] + ".html")
        code = _curl(u, out); time.sleep(0.3)
        if code != "200" and os.path.exists(out): os.remove(out)
        return u, code, out
    with cf.ThreadPoolExecutor(workers) as ex: res = list(ex.map(get, urls))
    return sum(1 for _, c, _ in res if c == "200")


def _txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_page(text, url, today):
    m = re.search(r"<h1>(.*?)</h1>", text, re.S)
    title = _txt(m.group(1)) if m else ""
    if not title: return []
    sub = re.search(r"</h1>\s*<p>(.*?)</p>", text, re.S)
    genre = re.search(r'class="genre [^"]*">\s*([^<\s][^<]*)<', text)
    cat = GENRE_CAT.get(_txt(genre.group(1)).lower(), "theatre") if genre else "theatre"
    out = []
    for d, body, cls1, txt1, cls2, txt2 in DATE_RX.findall(text):
        if d < today.isoformat(): continue
        t = re.search(r"(\d{1,2}):(\d{2})", _txt(body))
        ev = {"t": title, "d": d, "v": "DeLaMar", "u": url, "c": cat, "s": "delamar"}
        if t: ev["h"] = f"{int(t.group(1)):02d}:{t.group(2)}"
        price = re.search(r"€\s*([\d.]+(?:,\d{1,2})?)", _txt(body))
        if price: ev["p"] = "from €" + price.group(1)
        if "disabled" in (cls1 or cls2) or re.search(r"uitverkocht|sold out", txt1 or txt2 or "", re.I): ev["so"] = 1
        if sub: ev["b"] = _txt(sub.group(1))[:120]
        out.append(ev)
    return out


def parse_pages(pages, today):
    """pages: list of (url, html) pairs."""
    out = []
    for url, text in pages: out += parse_page(text, url, today)
    return out
