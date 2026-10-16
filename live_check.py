"""Development check (manual dump workflow only): compare plain HTTP with a real browser for the price readers.

Picks a few upcoming events per source in pageprices.READERS, reads each page both ways, runs the source's reader
on both texts and reports per source: how many pages loaded each way, and whether the two answers agree. Sources
where plain HTTP loses prices belong in pageprices.RENDER. Writes _data/probe/live_check.tsv.
"""
import asyncio, collections, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pageprices as pp

PER = int(os.environ.get("LIVE_CHECK_PER", "6"))
OUT = os.path.join(HERE, "_data", "probe")


def main():
    raw = subprocess.run(["curl", "-sS", "-m", "90", "https://whatsonadam.github.io/whats-on-adam/events.json"], capture_output=True, text=True).stdout
    ev = [e for e in json.loads(raw)["events"] if e["s"] in pp.READERS and e["c"] != "film" and not e.get("p") and e.get("u", "").startswith("http")]
    by = collections.defaultdict(list)
    for e in sorted(ev, key=lambda e: e["d"]):
        if e["u"] not in {x["u"] for x in by[e["s"]]}:
            by[e["s"]].append(e)
    chosen = [e for s, items in by.items() for e in items[:PER]]
    urls = [e["u"] for e in chosen]
    t = time.monotonic()
    http = pp._fetch_http(urls, time.monotonic() + 600)
    t_http = time.monotonic() - t
    t = time.monotonic()
    browser = asyncio.run(pp._fetch_all(urls, 600))
    t_browser = time.monotonic() - t
    print(f"{len(urls)} pages: HTTP {int(t_http)}s, browser {int(t_browser)}s", flush=True)
    os.makedirs(OUT, exist_ok=True)
    rows, stats = [], collections.defaultdict(lambda: collections.Counter())
    for e in chosen:
        h, b = http.get(e["u"]), browser.get(e["u"])
        ph = pp.read(e["s"], h) if h else None
        pb = pp.read(e["s"], b) if b else None
        st = stats[e["s"]]
        st["pages"] += 1; st["http_loaded"] += h is not None; st["browser_loaded"] += b is not None
        st["http_price"] += bool(ph); st["browser_price"] += bool(pb)
        st["same"] += (ph == pb); st["differ"] += (ph != pb)
        rows.append("\t".join([e["s"], e["d"], str(ph), str(pb), "" if ph == pb else "DIFF", e["t"][:50], e["u"]]))
    open(os.path.join(OUT, "live_check.tsv"), "w").write("\n".join(rows) + "\n")
    for s, c in sorted(stats.items()):
        print(f"{s:16} pages {c['pages']}  loaded http {c['http_loaded']} browser {c['browser_loaded']}  "
              f"price http {c['http_price']} browser {c['browser_price']}  same {c['same']} differ {c['differ']}", flush=True)


if __name__ == "__main__":
    main()
