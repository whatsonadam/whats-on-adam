"""Development probe: why do some Paradiso/Paylogic ticket pages come back without a price in the browser?
Opens ticket pages of upcoming Tolhuistuin events in several ways (plain, wait longer, retry, one at a time)."""
import asyncio, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pageprices as pp
from fetch import to_md, UA

async def main():
    from playwright.async_api import async_playwright
    raw = subprocess.run(["curl", "-sS", "-m", "90", "https://whatsonadam.github.io/whats-on-adam/events.json"], capture_output=True, text=True).stdout
    ev = sorted([e for e in json.loads(raw)["events"] if e["s"] == "tolhuistuin" and e["c"] != "film" and not e.get("p")], key=lambda e: e["d"])
    urls = list(dict.fromkeys(e["u"] for e in ev))[:8]
    pages = pp._fetch_http(urls, time.monotonic() + 120)
    shops = [pp.link_paradiso(pages[u], u) for u in urls if pages.get(u)]
    shops = [s for s in shops if s]
    print(len(urls), "event pages;", len(shops), "paradiso links", flush=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        for mode in ("plain", "block", "retry"):
            ok = 0
            for s in shops:
                ctx = await browser.new_context(user_agent=UA, locale="en-GB")
                page = await ctx.new_page()
                if mode == "block":
                    await page.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "font", "media") else r.continue_())
                txt = ""
                for attempt in range(2 if mode == "retry" else 1):
                    try:
                        await page.goto(s, timeout=40000, wait_until="networkidle" if mode != "block" else "domcontentloaded")
                        await page.wait_for_timeout(4000)
                        txt = to_md(await page.content())
                    except Exception as ex:
                        txt = "ERR " + str(ex)[:80]
                    if pp.read_paylogic(txt):
                        break
                got = pp.read_paylogic(txt)
                ok += bool(got)
                print(f"{mode:6} {s[-12:]} -> {got} final={page.url[-60:]} len={len(txt)}", flush=True)
                await ctx.close()
            print(f"== {mode}: {ok}/{len(shops)}", flush=True)
        await browser.close()

asyncio.run(main())
