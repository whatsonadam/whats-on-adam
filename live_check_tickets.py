"""Development check (manual dump workflow only): second hop for ticket-shop venues.

For sources in pageprices.FOLLOW, reads event pages (HTTP), finds the ticket shop link, then loads the shop page
both by plain HTTP and in a real browser and compares what the shop readers find. Shop hosts where HTTP loses
prices belong in pageprices.RENDER_HOSTS. Writes _data/probe/live_check_tickets.tsv.
"""
import asyncio, collections, json, os, subprocess, sys, time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pageprices as pp

PER = int(os.environ.get("LIVE_CHECK_PER", "8"))
OUT = os.path.join(HERE, "_data", "probe")


def main():
    raw = subprocess.run(["curl", "-sS", "-m", "90", "https://whatsonadam.github.io/whats-on-adam/events.json"], capture_output=True, text=True).stdout
    ev = [e for e in json.loads(raw)["events"] if e["s"] in pp.FOLLOW and e["c"] != "film" and not e.get("p") and e.get("u", "").startswith("http")]
    by = collections.defaultdict(list)
    for e in sorted(ev, key=lambda e: e["d"]):
        if e["u"] not in {x["u"] for x in by[e["s"]]}:
            by[e["s"]].append(e)
    chosen = [e for s, items in by.items() for e in items[:PER]]
    pages = pp._fetch_http([e["u"] for e in chosen], time.monotonic() + 300)
    hops = {}
    for e in chosen:
        t = pages.get(e["u"])
        hops[e["u"]] = pp.FOLLOW[e["s"]](t, e["u"]) if t else None
    shops = sorted({h for h in hops.values() if h})
    t = time.monotonic(); http = pp._fetch_http(shops, time.monotonic() + 300); th = time.monotonic() - t
    t = time.monotonic(); br = asyncio.run(pp._fetch_all(shops, 300)); tb = time.monotonic() - t
    print(f"{len(chosen)} events, {len(shops)} shop pages: HTTP {int(th)}s, browser {int(tb)}s", flush=True)
    rows, stats = [], collections.defaultdict(collections.Counter)
    for e in chosen:
        tk = hops[e["u"]]
        h, b = (http.get(tk), br.get(tk)) if tk else (None, None)
        ph = pp.read_ticket_page(tk, h) if h else None
        pb = pp.read_ticket_page(tk, b) if b else None
        st = stats[(e["s"], urlparse(tk).netloc if tk else "-")]
        st["events"] += 1; st["http_loaded"] += h is not None; st["browser_loaded"] += b is not None
        st["http_price"] += bool(ph); st["browser_price"] += bool(pb); st["differ"] += (ph != pb)
        rows.append("\t".join([e["s"], e["d"], str(ph), str(pb), "" if ph == pb else "DIFF", e["t"][:40], str(tk)]))
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "live_check_tickets.tsv"), "w").write("\n".join(rows) + "\n")
    for (s, host), c in sorted(stats.items()):
        print(f"{s:14} {host:30} events {c['events']} loaded http {c['http_loaded']} browser {c['browser_loaded']} "
              f"price http {c['http_price']} browser {c['browser_price']} differ {c['differ']}", flush=True)


if __name__ == "__main__":
    main()
