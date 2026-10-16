"""Development probe (run by the manual "Dump source data" workflow, never by a refresh).

Takes the live events.json, picks a few event pages per source that has little or no price data,
opens each in headless Chromium and saves the page text to _data/probe/pages/<source>__<n>.md plus
an index.json. Used to see which sources show a clean price on the event page itself.
"""
import asyncio, json, os, re, subprocess, collections, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_data", "probe", "pages")
LIVE = "https://whatsonadam.github.io/whats-on-adam/events.json"
PER_SOURCE = 4
SKIP = {"ade"}


def pick():
    raw = subprocess.run(["curl", "-sS", "-m", "90", LIVE], capture_output=True, text=True).stdout
    ev = json.loads(raw)["events"]
    by = collections.defaultdict(list)
    for e in ev:
        if e["c"] == "film" or e["s"] in SKIP or not e.get("u"):
            continue
        by[e["s"]].append(e)
    chosen = []
    for s, items in by.items():
        priced = sum(1 for e in items if e.get("p"))
        if priced / len(items) > 0.6:
            continue
        seen, n = set(), 0
        for e in sorted(items, key=lambda x: x["d"]):
            if e["u"] in seen or not e["u"].startswith("http"):
                continue
            seen.add(e["u"]); chosen.append((s, n, e)); n += 1
            if n >= PER_SOURCE:
                break
    return chosen


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
                rec = {"source": s, "n": n, "title": e["t"], "url": e["u"], "date": e["d"], "known_price": e.get("p")}
                try:
                    r = await page.goto(e["u"], timeout=40000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3500)
                    rec["status"] = r.status if r else 0
                    md = to_md(await page.content())
                    open(os.path.join(OUT, f"{s}__{n}.md"), "w").write(f"URL: {e['u']}\n\n{md}")
                    rec["chars"] = len(md)
                except Exception as ex:
                    rec["error"] = str(ex)[:120]
                finally:
                    await ctx.close()
                index.append(rec)

        await asyncio.gather(*[one(*c) for c in chosen])
        await browser.close()
    json.dump(index, open(os.path.join(HERE, "_data", "probe", "index.json"), "w"), indent=1)
    print(f"{len(index)} pages, {sum(1 for r in index if r.get('chars'))} saved")


if __name__ == "__main__":
    asyncio.run(run(pick()))
