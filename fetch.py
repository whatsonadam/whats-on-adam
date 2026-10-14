"""Step 1 of a refresh: download every source into _data/ (no AI involved).

    python3 fetch.py            # everything
    python3 fetch.py mezrab ot301   # only some keys

Venue pages are rendered in headless Chromium (Playwright) and saved as markdown
(_data/<key>.md); Cinetol is also saved as raw HTML. radar.squat.net comes from its
JSON API and I amsterdam from its listing pages. De Zwijger and The School of Life block
automated browsers: if their files come back as 'blocked', fetch them with WebFetch
(see README).
"""
import asyncio, datetime, json, os, re, subprocess, sys, time, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
NL_MONTHS = ["januari","februari","maart","april","mei","juni","juli","augustus","september","oktober","november","december"]

def cavia_urls(today):
    urls = {}
    for i in range(3):
        m = (today.month - 1 + i) % 12; y = today.year + (today.month - 1 + i) // 12
        urls[f"cavia_{i}"] = f"https://www.filmhuiscavia.nl/programma/{NL_MONTHS[m]}-{y}"
    return urls

PAGES = {
    "mezrab": "https://mezrab.nl/full-program/",
    "vrankrijk": "https://vrankrijk.org/events/",
    "aralez": "https://stichtingaralez.com/events/",
    "desering": "https://desering.org/events",
    "amsterdamalternative": "https://www.amsterdamalternative.nl/agenda",
    "offbeat": "https://offbeat.amsterdam/",
    "likeminds": "https://likeminds.nl/agenda/",
    "garagenoord": "https://www.garagenoord.com/club/9-lives-of-garage-noord",
    "skatecafe": "https://skatecafe.weticket.io/",
    "deceuvel": "https://deceuvel.nl/en/events/",
    "nieuweanita": "https://denieuweanita.nl/",
    "verzetsmuseum": "https://www.verzetsmuseum.org/nl/agenda",
    "wereldmuseum": "https://amsterdam.wereldmuseum.nl/",
    "odessa": "https://www.odessa.amsterdam/",
    "ot301": "https://ot301.nl/agenda",
    "cinetol": "https://www.cinetol.nl/programma",
    "ccamstel": "https://ccamstel.nl/programma",
    "volkshotel": "https://www.volkshotel.nl/en/agenda/",
    "lab111": "https://www.lab111.nl/programma/",
    "tolhuistuin": "https://tolhuistuin.nl/en/agenda",
    "dezwijger": "https://dezwijger.nl/agenda",
    "schooloflife": "https://www.theschooloflife.com/amsterdam/agenda/",
}
KEEP_HTML = {"cinetol"}
LOAD_MORE = {"tolhuistuin"}
BLOCKED_OK = {"schooloflife"}  # Claude writes this file via WebFetch, keep it
EMPTY_HINTS = ["Sorry, no events right now"]

def to_md(html):
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    s = BeautifulSoup(html, "html.parser")
    for t in s(["script", "style", "noscript", "svg", "iframe", "header", "footer"]): t.decompose()
    return re.sub(r"\n\s*\n+", "\n\n", md(str(s), strip=["img"], heading_style="ATX"))

async def render_one(browser, key, url, sem, status):
    async with sem:
        ctx = await browser.new_context(user_agent=UA, locale="en-GB")
        page = await ctx.new_page()
        try:
            r = await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            code = r.status if r else 0
            await page.wait_for_timeout(4000)
            for _ in range(4):
                await page.mouse.wheel(0, 4000); await page.wait_for_timeout(700)
            # some sites fill their agenda widget late; give them up to 20 more seconds
            for _ in range(10):
                body = await page.inner_text("body")
                if not any(s in body for s in EMPTY_HINTS): break
                await page.wait_for_timeout(2000)
            if key in LOAD_MORE:
                for _ in range(15):
                    btn = page.get_by_text(re.compile(r"(load more|meer laden|show more|toon meer)", re.I))
                    if await btn.count() == 0: break
                    try: await btn.last.click(timeout=4000); await page.wait_for_timeout(1800)
                    except Exception: break
            html = await page.content()
            if code >= 400:
                # drop any older copy so build.py never parses stale data
                for ext in (".md", ".html"):
                    f = os.path.join(DATA, key + ext)
                    if os.path.exists(f) and not (key in BLOCKED_OK and ext == ".md"): os.remove(f)
                status[key] = f"blocked ({code})"; return
            if key in KEEP_HTML:
                open(os.path.join(DATA, f"{key}.html"), "w").write(html)
            open(os.path.join(DATA, f"{key}.md"), "w").write(f"SOURCE: {url}\n\n" + to_md(html))
            status[key] = "ok"
        except Exception as e:
            status[key] = f"error: {str(e)[:80]}"
        finally:
            await ctx.close()

async def render_all(pages, status):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        sem = asyncio.Semaphore(6)
        await asyncio.gather(*[render_one(browser, k, u, sem, status) for k, u in pages.items()])
        await browser.close()

def curl(url, out):
    r = subprocess.run(["curl", "-sS", "-g", "-m", "60", "-A", UA, "-o", out, "-w", "%{http_code}", url], capture_output=True, text=True)
    return r.stdout.strip()

def fetch_radar(status):
    url = ("https://radar.squat.net/api/1.2/search/events.json?facets[city][]=Amsterdam"
           "&fields=title,date_time,offline,url,category&limit=500")
    out = os.path.join(DATA, "radar.json")
    for attempt in range(3):                      # the radar API sometimes times out; try a few times
        code = curl(url, out)
        try:
            json.load(open(out)); status["radar"] = "ok"; return
        except Exception:
            status["radar"] = f"error {code} (not valid data)"; time.sleep(5)
    os.remove(out)                                # build.py then keeps the previous radar events

def fetch_ade(status, today, max_pages=80):
    """ADE's public programme listing (JSON, 40 per page). Politely: one page per second, stops at the first empty page."""
    d = os.path.join(DATA, "ade"); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    to = today + datetime.timedelta(days=60)
    n = 0
    for p in range(max_pages):
        url = ("https://www.amsterdam-dance-event.nl/api/program/filter/?section=events&type=8262%2C8263"
               f"&from={today.isoformat()}&to={to.isoformat()}&page={p}")
        out = os.path.join(d, f"p{p:03d}.json")
        if curl(url, out) != "200": status["ade"] = f"error on page {p}"; return
        try: items = json.load(open(out)).get("data", [])
        except Exception: status["ade"] = f"unreadable page {p}"; return
        if not items: os.remove(out); break
        n += len(items); time.sleep(1.0)
    status["ade"] = f"ok ({n} listings)"

def fetch_cinemas(status, today):
    """Cinemas whose programme comes from an API or per-day request. Each writes one file in _data/ for its parser."""
    sys.path.insert(0, os.path.join(HERE, "parsers"))
    import eye, rialto, uitkijk, studiok, ketelhuis, cineville_common
    jobs = {
        "eye": lambda p: eye.fetch_json(today, p),
        "rialto": lambda p: rialto.fetch_text(today, p),
        "uitkijk": lambda p: uitkijk.fetch(p),
        "studiok": lambda p: studiok.fetch(p, today),
        "ketelhuis": lambda p: ketelhuis.fetch(p, today),
        "themovies": lambda p: curl("https://themovies.nl/fk-feed/agenda", p),
        "filmhallen": lambda p: curl("https://filmhallen.nl/fk-feed/agenda", p),
        "hyena": lambda p: curl("https://tickets.fchyena.nl/fchyena/nl/flow_configs/1/z_events_list", p),
        "cinecenter": lambda p: curl("https://www.cinecenter.nl/programma", p),
        "melkwegcinema": lambda p: curl("https://www.melkweg.nl/nl/agenda/", p),
        "filmladder": lambda p: curl("https://www.filmladder.nl/amsterdam/bioscopen", p),
    }
    for k in ("amstelveen", "devlugt", "thepulse", "omval", "docpaviljoen", "kriterion"):
        jobs[k] = (lambda kk: lambda p: cineville_common.fetch_venue(kk, today, p))(k)
    for k, job in jobs.items():
        out = os.path.join(DATA, f"{k}.cin")
        try:
            job(out)
            status[k] = "ok" if os.path.exists(out) and os.path.getsize(out) > 20 else "empty"
        except Exception as ex:
            status[k] = f"error {str(ex)[:60]}"
        time.sleep(1.0)

def fetch_iamsterdam(status, max_pages=300):
    d = os.path.join(DATA, "iamsterdam"); os.makedirs(d, exist_ok=True)
    for f in os.listdir(d): os.remove(os.path.join(d, f))
    def get(p):
        out = os.path.join(d, f"p{p:03d}.html")
        return p, curl(f"https://www.iamsterdam.com/uit/agenda?page={p}", out), out
    # probe the first page for the result count so we only fetch what exists
    _, code, first = get(1)
    total = 4200
    try:
        m = re.search(r"([\d.]+) resultaten", open(first, errors="ignore").read())
        if m: total = int(m.group(1).replace(".", ""))
    except Exception: pass
    pages = min(max_pages, total // 16 + 2)
    with cf.ThreadPoolExecutor(6) as ex:
        res = list(ex.map(get, range(2, pages + 1)))
    bad = [p for p, c, _ in res if c != "200"]
    status["iamsterdam"] = f"ok ({pages} pages{', %d failed' % len(bad) if bad else ''})"

def fetch_extras(status, today, want):
    """Sources read from an API or a plain page, no browser needed. Each failure keeps the previous data (see build.py)."""
    sys.path.insert(0, os.path.join(HERE, "parsers"))
    if not want or "ra" in want:
        import ra
        try: status["ra"] = f"ok ({ra.fetch(os.path.join(DATA, 'ra'), today)} listings)"
        except Exception as ex:
            status["ra"] = f"error {str(ex)[:60]}"
            import shutil; shutil.rmtree(os.path.join(DATA, "ra"), ignore_errors=True)   # build.py then keeps the previous RA events
    if not want or "delamar" in want:
        import delamar
        try: status["delamar"] = f"ok ({delamar.fetch(os.path.join(DATA, 'delamar'))} show pages)"
        except Exception as ex:
            status["delamar"] = f"error {str(ex)[:60]}"
            import shutil; shutil.rmtree(os.path.join(DATA, "delamar"), ignore_errors=True)   # build.py then keeps the previous events
    if not want or "offlineclub" in want:
        import offlineclub
        out = os.path.join(DATA, "offlineclub.html")
        code = offlineclub.fetch(out)
        if code != "200":
            status["offlineclub"] = f"error {code}"
            if os.path.exists(out): os.remove(out)
        else: status["offlineclub"] = "ok"

def main():
    os.makedirs(DATA, exist_ok=True)
    today = datetime.date.today()
    want = set(sys.argv[1:])
    pages = dict(PAGES); pages.update(cavia_urls(today))
    if want: pages = {k: v for k, v in pages.items() if k in want or (k.startswith("cavia") and "cavia" in want)}
    status = {}
    if pages: asyncio.run(render_all(pages, status))
    if not want or "radar" in want: fetch_radar(status)
    if not want or "iamsterdam" in want: fetch_iamsterdam(status)
    if not want or "ade" in want: fetch_ade(status, today)
    if not want or "cinemas" in want: fetch_cinemas(status, today)
    fetch_extras(status, today, want)
    json.dump({"fetched": today.isoformat(), "status": status}, open(os.path.join(DATA, "fetch_status.json"), "w"), indent=1)
    for k in sorted(status): print(f"{k:22} {status[k]}")

if __name__ == "__main__":
    main()
