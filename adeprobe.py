"""One-off probe: how does the ADE programme page deliver its events? Prints findings to the log."""
from playwright.sync_api import sync_playwright
U = "https://www.amsterdam-dance-event.nl/en/program/filter/?section=events&type=8262%2C8263&from=2026-10-21&to=2026-10-25"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 900})
    seen = []
    pg.on("response", lambda r: seen.append((r.status, r.request.resource_type, r.url[:200])) if r.request.resource_type in ("xhr", "fetch") and "amsterdam-dance-event" in r.url else None)
    pg.goto(U, wait_until="domcontentloaded", timeout=90000); pg.wait_for_timeout(15000)
    print("URL:", pg.url)
    for s in seen: print("REQ", s)
    t = pg.inner_text("body"); print("TEXT LEN", len(t)); print(t[:1500])
    links = pg.eval_on_selector_all("a[href]", "els=>els.map(e=>e.href)")
    ev = [l for l in links if "/program/" in l or "/event" in l]
    print("LINKS", len(links), "program-ish", len(ev)); print("\n".join(ev[:40]))
    open("ade_probe.html", "w").write(pg.content())
    b.close()
