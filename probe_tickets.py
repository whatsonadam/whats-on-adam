"""Development probe (manual dump workflow only): follow the ticket link on event pages.

For sources whose own event page shows no price, open a few event pages, find the ticket links, open the
first external one and save its text. This shows which ticket platforms are involved and what a price
looks like there. Output: _data/probe/tickets/<source>__<n>__{page,ticket}.md and tickets_index.json.
"""
import asyncio, collections, json, os, re, subprocess, sys
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_data", "probe", "tickets")
LIVE = "https://whatsonadam.github.io/whats-on-adam/events.json"
SOURCES = ["cinetol", "ccamstel", "parallel", "radion", "opsolder", "skatecafe", "nieuweanita", "prik", "tanker",
           "dehallen", "likeminds", "wereldmuseum", "grachten", "brecht", "socialisme", "watkanikdoen", "garagenoord",
           "desering", "tolhuistuin", "amsterdammuseum", "verzetsmuseum", "offbeat", "mezrab", "odessa", "dezwijger",
           "vrankrijk", "volkshotel", "ot301", "deceuvel", "frascati", "melkweg", "paradiso", "occii"]
PER = 3
TICKET_WORDS = re.compile(r"ticket|tickets|kaart|koop|bestel|buy|order|reserv|rsvp|inschrijv|aanmeld|boek|book", re.I)


def pick():
    raw = subprocess.run(["curl", "-sS", "-m", "90", LIVE], capture_output=True, text=True).stdout
    ev = [e for e in json.loads(raw)["events"] if e["c"] != "film" and e.get("u", "").startswith("http")]
    by = collections.defaultdict(list)
    for e in ev:
        if e["s"] in SOURCES:
            by[e["s"]].append(e)
    out = []
    for s, items in by.items():
        seen = set()
        for e in sorted(items, key=lambda x: x["d"]):
            if e["u"] in seen:
                continue
            seen.add(e["u"]); out.append((s, len(seen) - 1, e))
            if len(seen) >= PER:
                break
    return out


async def run(chosen):
    from playwright.async_api import async_playwright
    sys.path.insert(0, HERE)
    from fetch import to_md, UA
    os.makedirs(OUT, exist_ok=True)
    index = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        sem = asyncio.Semaphore(4)

        async def one(s, n, e):
            async with sem:
                ctx = await browser.new_context(user_agent=UA, locale="en-GB")
                page = await ctx.new_page()
                rec = {"source": s, "n": n, "title": e["t"], "url": e["u"], "known_price": e.get("p"), "links": []}
                try:
                    await page.goto(e["u"], timeout=40000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                    open(os.path.join(OUT, f"{s}__{n}__page.md"), "w").write(f"URL: {e['u']}\n\n{to_md(html)}")
                    links = await page.eval_on_selector_all(
                        "a[href]", "els => els.map(a => [a.innerText.trim().slice(0,60), a.href])")
                    here = urlparse(e["u"]).netloc
                    cand = [(t, h) for t, h in links if TICKET_WORDS.search(t) and h.startswith("http") and urlparse(h).netloc != here]
                    rec["links"] = cand[:4]
                    if cand:
                        tp = await ctx.new_page()
                        try:
                            await tp.goto(cand[0][1], timeout=40000, wait_until="domcontentloaded")
                            await tp.wait_for_timeout(4000)
                            th = await tp.content()
                            rec["ticket_host"] = urlparse(tp.url).netloc
                            open(os.path.join(OUT, f"{s}__{n}__ticket.md"), "w").write(f"URL: {tp.url}\n\n{to_md(th)}")
                        except Exception as ex:
                            rec["ticket_error"] = str(ex)[:100]
                except Exception as ex:
                    rec["error"] = str(ex)[:120]
                finally:
                    await ctx.close()
                index.append(rec)

        await asyncio.gather(*[one(*c) for c in chosen])
        await browser.close()
    json.dump(index, open(os.path.join(HERE, "_data", "probe", "tickets_index.json"), "w"), indent=1)
    print(len(index), "pages;", sum(1 for r in index if r.get("ticket_host")), "ticket pages")


if __name__ == "__main__":
    asyncio.run(run(pick()))
