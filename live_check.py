"""Development check (manual dump workflow only): run the real price readers on live event pages.

Picks a few upcoming events per source in pageprices.READERS, fetches them exactly as a refresh would, and writes
_data/probe/live_check.tsv (source, date, price read, title, url) plus the page text of every page where no
price was read, so each answer can be compared with what the page really says.
"""
import collections, json, os, subprocess, sys, asyncio, datetime

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
    os.makedirs(os.path.join(OUT, "live_none"), exist_ok=True)
    pages = asyncio.run(pp._fetch_all([e["u"] for e in chosen]))
    rows, stats = [], collections.defaultdict(lambda: [0, 0, 0])
    for i, e in enumerate(chosen):
        text = pages.get(e["u"])
        p = pp.read(e["s"], text) if text else None
        st = stats[e["s"]]; st[0] += 1; st[1] += bool(p); st[2] += text is None
        rows.append("\t".join([e["s"], e["d"], str(p), "UNREADABLE" if text is None else "", e["t"][:60], e["u"]]))
        if text is not None and not p:
            open(os.path.join(OUT, "live_none", f"{e['s']}__{i}.md"), "w").write(f"URL: {e['u']}\n\n{text}")
    open(os.path.join(OUT, "live_check.tsv"), "w").write("\n".join(rows) + "\n")
    for s, (n, hit, bad) in sorted(stats.items()):
        print(f"{s:16} read {n - bad}/{n}  price {hit}  unreadable {bad}")


if __name__ == "__main__":
    main()
