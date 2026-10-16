"""Development check (manual dump workflow only): run the production price step on live events and time it.

Uses the live events.json as input and the same pageprices.fill() a refresh runs, with the same limits, then
prints how long it took and how many prices each source gave. Writes prices.json next to this file (not committed).
"""
import datetime, json, subprocess, sys, time, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pageprices as pp

raw = subprocess.run(["curl", "-sS", "-m", "90", "https://whatsonadam.github.io/whats-on-adam/events.json"], capture_output=True, text=True).stdout
events = json.loads(raw)["events"]
t = time.time()
st = pp.fill(events, datetime.date.today())
print(f"price step took {int(time.time() - t)}s:", {k: v for k, v in st.items() if k != "by_source"}, flush=True)
for s, x in sorted(st["by_source"].items()):
    print(f"  {s:16} read {x['read']:4} price {x['price']:4} unreadable {x['unreadable']:3}", flush=True)
