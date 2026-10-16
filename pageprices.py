"""Fill in missing prices by reading each event's own page, once.

Many agenda pages list no price, but the event page does, in a fixed spot ("Koop tickets vanaf €15",
"Entrance: Donation based", "Prijs: Gratis"). For the sources in READERS this opens the event page in headless
Chromium, runs that source's reader and saves the result in prices.json. Later runs reuse the saved answer, so
only new events cost a page visit.

Accuracy rules (see tests/test_pageprices.py):
  * a reader looks only at the one place where its source states the price, never at stray euro signs;
  * "Free" is only recorded when the page says the event itself is free, not "free with a museum ticket";
  * when a reader finds nothing it returns None and the event simply shows no price;
  * prices are what a visitor pays, so they include VAT.

Politeness: browser user agent as in fetch.py, 1 second between requests to the same site, at most MAX_FETCH
pages per run (the quickest-coming events first), images and fonts not downloaded.
"""
import asyncio, concurrent.futures as cf, datetime, json, os, re, subprocess, sys, threading, time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "parsers"))
from _price import clean  # noqa: E402

CACHE = os.path.join(HERE, "prices.json")
MAX_FETCH = int(os.environ.get("PAGE_PRICES_MAX", "500"))
RECHECK_FOUND_DAYS = 21      # a price we found: look again after three weeks (prices change)
RECHECK_MISSING_DAYS = 7     # nothing found: try again after a week
HOST_GAP = 1.0               # seconds between requests to the same site
CONCURRENCY = 4
PAGE_TIMEOUT_MS = 25000
BUDGET_SECONDS = int(os.environ.get("PAGE_PRICES_BUDGET", "420"))   # the whole price step never runs longer than this
HOST_MAX_FAILS = 3           # a site that fails this many times in a row is skipped for the rest of the run
HTTP_WORKERS = 6
RENDER = {"radar"}           # sources whose pages need a real browser to show the price (all others: plain HTTP, much faster)
LOOKAHEAD_DAYS = 120


def _m(pattern, text, flags=re.M | re.I):
    return re.search(pattern, text, flags)


def _donation(text):
    return bool(re.search(r"donation|donatie|vrijwillige bijdrage|pay what you|whatever you think", text, re.I))


# ---------------------------------------------------------------- readers (one per source)

def read_iamsterdam(t):
    """'Koop tickets vanaf €15' is a fixed component of every ticketed event page; the first one is the event's own."""
    m = _m(r"Koop tickets vanaf\s*€\s*(\d+(?:[.,]\d{1,2})?)", t)
    return clean(m.group(1) + "+") if m else None


def read_mezrab(t):
    m = _m(r"^Price\s*\*\*\s*€\s*([\d.,]+)\s*\*\*", t)
    if m:
        return clean("€" + m.group(1))
    m = _m(r"^Entrance:?\s*(.{1,80})$", t)
    if m:
        v = m.group(1)
        if re.match(r"free|gratis", v, re.I):
            return "Free"
        if _donation(v):
            return "Donation"
        return clean(v) if "€" in v else None
    if _m(r"^Entrance is whatever you think", t):
        return "Donation"
    return "Free" if _m(r"^Free admission\b", t) else None


def read_tolhuistuin(t):
    m = _m(r"\bEntrance\s+(.{1,40}?)\s+Location\b", t, re.I)
    return clean(m.group(1)) if m else None


def read_cinetol(t):
    m = _m(r"TICKET:\s*€\s*([\d.,]+)", t, re.I | re.S)
    return clean("€" + m.group(1)) if m else None


def read_radar(t):
    """radar.squat.net event pages have a 'Price:' section; its first line is the price as the organiser wrote it."""
    m = _m(r"^#{1,4}\s*Price:?\s*\n+\s*(?:[*-]\s*)?(.+)$", t)
    if not m:
        return None
    v = m.group(1).strip()
    if len(v) > 60:
        return None
    if re.match(r"(free|gratis)\b", v, re.I) and not re.search(r"\d|€", v):
        return "Free"
    if _donation(v) and "€" not in v:
        return "Donation"
    return clean(v) if re.search(r"€|\beuro\b|\d", v) else None


def read_amsterdammuseum(t):
    m = _m(r"^\*\*Price\*\*:?\s*(.+)$", t)
    if not m:
        return None
    v = m.group(1).strip()
    return clean(v) if re.match(r"€\s*\d", v) else None   # "Free with a valid entry ticket" is not free


def read_verzetsmuseum(t):
    m = _m(r"^\*\*Prijs:?\*\*:?\s*(.+)$", t)
    if not m:
        return None
    v = m.group(1)
    reg = _m(r"€\s*([\d.,]+)\s+regulier", v)
    if reg:
        return clean("€" + reg.group(1))
    first = _m(r"^€\s*([\d.,]+)", v)
    return clean("€" + first.group(1)) if first else None


def read_verbroederij(t):
    m = _m(r"^\*\*Toegang\?\*\*\s*(.+)$", t)
    if not m:
        return None
    v = m.group(1).strip()
    if re.match(r"gratis\b", v, re.I):
        return "Free"
    return clean(v) if re.match(r"€\s*\d", v) else None


def read_xr(t):
    m = _m(r"^Prijs:\s*(.+)$", t)
    if not m:
        return None
    v = m.group(1).strip()
    if re.match(r"gratis\b", v, re.I):
        return "Free"
    if _donation(v):
        return "Donation"
    return clean(v) if re.match(r"€\s*\d", v) else None


def read_iisg(t):
    m = _m(r"^(?:\*\*)?Entree:?(?:\*\*)?:?\s*(.+)$", t)
    v = m.group(1).strip() if m else None
    if v is None:
        m = _m(r"^(Vrije toegang)\b", t)
        v = m.group(1) if m else None
    if not v:
        return None
    if re.match(r"(vrije toegang|gratis)\b", v, re.I):
        return "Free"
    return clean(v) if re.match(r"€\s*\d", v) else None


def read_marineterrein(t):
    return "Free" if _m(r"^Gratis entree\b", t) else None


def read_offbeat(t):
    m = _m(r"minimum suggested donation is\s*€\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        return "Donation, min " + clean("€" + m.group(1))
    return "Donation" if _m(r"suggested donation", t) else None


def read_odessa(t):
    """Odessa sells through hipsy.nl. The ticket tiers sit between 'Bekijk op kaart' and 'Boek nu'; the lowest is the price."""
    seg = _m(r"Bekijk op kaart(.*?)Boek nu", t, re.S)
    if not seg:
        return None
    prices = [float(x.replace(".", "").replace(",", ".")) for x in re.findall(r"^€\s*(\d+(?:[.,]\d{1,2})?)\s*$", seg.group(1), re.M)]
    prices = [p for p in prices if p > 0]
    return clean(f"{min(prices):.2f}" + "+") if prices else None


def read_dezwijger(t):
    """tickets.dezwijger.nl: under 'Kies tickets en prijzen' the line 'Ticket' is followed by its price."""
    m = _m(r"Kies tickets en prijzen.*?^Ticket\s*\n+\s*€\s*(\d+(?:[.,]\d{1,2})?)", t, re.M | re.S)
    if m:
        return clean("€" + m.group(1))
    block = _m(r"Kies tickets en prijzen(.*?)Totaal", t, re.S)
    if block and "€" not in block.group(1) and re.search(r"^Vrijkaart\s*$", block.group(1), re.M):
        return "Free"   # the only ticket type on offer is a free one
    return None


READERS = {
    "iamsterdam": read_iamsterdam, "mezrab": read_mezrab, "tolhuistuin": read_tolhuistuin, "cinetol": read_cinetol,
    "radar": read_radar, "amsterdammuseum": read_amsterdammuseum, "verzetsmuseum": read_verzetsmuseum,
    "verbroederij": read_verbroederij, "xr": read_xr, "iisg": read_iisg, "marineterrein": read_marineterrein,
    "offbeat": read_offbeat, "odessa": read_odessa, "dezwijger": read_dezwijger,
}


def read(source, text):
    fn = READERS.get(source)
    if not fn or not text:
        return None
    try:
        return fn(text)
    except Exception:
        return None


# ---------------------------------------------------------------- fetching and cache

def _fetch_http(urls, deadline):
    """Plain HTTP download of each page (like pagetimes.py), converted to the same markdown the readers expect.
    Returns {url: text or None}. Pages not reached before the deadline are missing from the result."""
    from fetch import to_md, UA
    out, fails, last = {}, {}, {}
    mu = threading.Lock()
    host_locks = {}

    def work(url):
        host = urlparse(url).netloc
        with mu:
            hl = host_locks.setdefault(host, threading.Lock())
        with hl:   # one request at a time per site, with a pause
            if time.monotonic() > deadline or fails.get(host, 0) >= HOST_MAX_FAILS:
                return
            wait = HOST_GAP - (time.monotonic() - last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            last[host] = time.monotonic()
        try:
            r = subprocess.run(["curl", "-sS", "-L", "--compressed", "-m", "25", "-A", UA, "-w", "\n%{http_code}", url],
                               capture_output=True, text=True)
            body, _, code = r.stdout.rpartition("\n")
            text = to_md(body) if code.strip() == "200" and body else None
        except Exception:
            text = None
        with mu:
            out[url] = text
            fails[host] = 0 if text else fails.get(host, 0) + 1
            if len(out) % 50 == 0:
                print(f"    ...{len(out)}/{len(urls)} pages by HTTP", flush=True)

    with cf.ThreadPoolExecutor(HTTP_WORKERS) as ex:
        list(ex.map(work, urls))
    return out


async def _fetch_all(urls, budget=None):
    """Return {url: markdown text or None}. None means the page could not be read (not 'no price').
    Stops after BUDGET_SECONDS; pages not reached are simply missing from the result and tried again next run."""
    from playwright.async_api import async_playwright
    from fetch import to_md, UA
    out = {}
    locks, last, fails = {}, {}, {}
    started = time.monotonic()
    sem = asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()

        async def one(url):
            host = urlparse(url).netloc
            lock = locks.setdefault(host, asyncio.Lock())
            async with sem:
                if fails.get(host, 0) >= HOST_MAX_FAILS:
                    return   # this site keeps failing: leave its pages for the next run
                async with lock:   # one request at a time per site, with a pause
                    wait = HOST_GAP - (time.monotonic() - last.get(host, 0))
                    if wait > 0:
                        await asyncio.sleep(wait)
                    last[host] = time.monotonic()
                ctx = await browser.new_context(user_agent=UA, locale="en-GB")
                page = await ctx.new_page()
                try:
                    await page.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "font", "media") else r.continue_())
                    resp = await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2500)
                    ok = bool(resp and resp.status < 400)
                    out[url] = to_md(await page.content()) if ok else None
                    fails[host] = 0 if ok else fails.get(host, 0) + 1
                except Exception:
                    out[url] = None
                    fails[host] = fails.get(host, 0) + 1
                finally:
                    await ctx.close()
                if len(out) % 25 == 0:
                    print(f"    ...{len(out)}/{len(urls)} pages after {int(time.monotonic() - started)}s", flush=True)

        tasks = [asyncio.ensure_future(one(u)) for u in urls]
        budget = BUDGET_SECONDS if budget is None else budget
        _, pending = await asyncio.wait(tasks, timeout=budget)
        if pending:
            print(f"    time budget of {int(budget)}s reached: {len(pending)} browser pages left for the next run", flush=True)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        await browser.close()
    return out


def _load():
    try:
        return json.load(open(CACHE))
    except Exception:
        return {}


def _fresh(entry, today):
    try:
        age = (today - datetime.date.fromisoformat(entry["t"])).days
    except Exception:
        return False
    return age < (RECHECK_FOUND_DAYS if entry.get("p") else RECHECK_MISSING_DAYS)


def fill(events, today, max_fetch=None):
    """Add 'p' to events that have none, from the cache and from up to max_fetch new page reads. Returns stats."""
    max_fetch = MAX_FETCH if max_fetch is None else max_fetch
    cache = _load()
    horizon = (today + datetime.timedelta(days=LOOKAHEAD_DAYS)).isoformat()
    wanted = {}   # url -> (earliest date, source)
    for e in events:
        if e.get("p") or e.get("c") == "film" or e.get("s") not in READERS or not (e.get("u") or "").startswith("http"):
            continue
        if e["d"] > horizon:
            continue
        cur = wanted.get(e["u"])
        if not cur or e["d"] < cur[0]:
            wanted[e["u"]] = (e["d"], e["s"])
    todo = sorted((u for u in wanted if not (u in cache and _fresh(cache[u], today))), key=lambda u: wanted[u][0])[:max_fetch]
    stats = {"wanted": len(wanted), "fetched": 0, "unreadable": 0, "found": 0, "by_source": {}}
    if todo and max_fetch > 0:
        t0 = time.monotonic()
        by_http = [u for u in todo if wanted[u][1] not in RENDER]
        by_browser = [u for u in todo if wanted[u][1] in RENDER]
        # plain HTTP gets 65% of the budget so the slower browser pages always have time left
        pages = _fetch_http(by_http, t0 + (0.65 if by_browser else 1.0) * BUDGET_SECONDS) if by_http else {}
        if by_browser:
            pages.update(asyncio.run(_fetch_all(by_browser, max(60, BUDGET_SECONDS - (time.monotonic() - t0)))))
        stats["not_reached"] = 0
        for u in todo:
            if u not in pages:
                stats["not_reached"] += 1   # ran out of time or the site was skipped: next run
                continue
            text = pages.get(u)
            src = wanted[u][1]
            st = stats["by_source"].setdefault(src, {"read": 0, "price": 0, "unreadable": 0})
            if text is None:
                stats["unreadable"] += 1; st["unreadable"] += 1
                continue
            p = read(src, text)
            cache[u] = {"p": p, "t": today.isoformat()}
            stats["fetched"] += 1; st["read"] += 1
            if p:
                stats["found"] += 1; st["price"] += 1
    n = 0
    for e in events:
        if e.get("p") or e.get("c") == "film" or e.get("s") not in READERS:
            continue
        c = cache.get(e.get("u"))
        if c and c.get("p"):
            e["p"] = c["p"]; n += 1
    stats["applied"] = n
    keep = {u: c for u, c in cache.items() if u in wanted or (c.get("t") or "") >= (today - datetime.timedelta(days=60)).isoformat()}
    json.dump(keep, open(CACHE, "w"), indent=0, sort_keys=True, ensure_ascii=False)
    return stats


if __name__ == "__main__":
    # python3 pageprices.py SOURCE FILE.md : run one reader on a saved page (for testing)
    print(read(sys.argv[1], open(sys.argv[2], errors="ignore").read()))
