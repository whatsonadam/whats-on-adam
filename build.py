"""Step 2 of a refresh: parse everything in _data/ and write the agenda page (no AI involved).

    python3 build.py [output.html] [--previous old.html]

Prints events per source and flags sources that returned nothing or dropped sharply
compared with the previous page; those parsers probably need a small fix because the
venue changed its website.
"""
import datetime, glob, importlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "_data")
sys.path.insert(0, os.path.join(HERE, "parsers"))

AGG = {"radar", "offbeat", "amsterdamalternative", "iamsterdam"}
# Page keys whose markdown feeds a parser of the same name
MD_KEYS = ["mezrab", "vrankrijk", "aralez", "desering", "amsterdamalternative", "offbeat", "likeminds",
           "garagenoord", "skatecafe", "deceuvel", "nieuweanita", "verzetsmuseum", "wereldmuseum", "odessa",
           "ot301", "ccamstel", "volkshotel", "lab111", "tolhuistuin", "dezwijger", "schooloflife"]

SOURCES = {
    "mezrab": ("Mezrab", "https://mezrab.nl/full-program/"),
    "vrankrijk": ("Vrankrijk", "https://vrankrijk.org/events/"),
    "aralez": ("Stichting Aralez", "https://stichtingaralez.com/events/"),
    "desering": ("De Sering", "https://desering.org/events"),
    "amsterdamalternative": ("Amsterdam Alternative", "https://www.amsterdamalternative.nl/agenda"),
    "offbeat": ("offbeat amsterdam", "https://offbeat.amsterdam/"),
    "vondelbunker": ("Vondelbunker", "https://www.hiddenagenda.nl/venues/vondelbunker"),
    "likeminds": ("Likeminds", "https://likeminds.nl/agenda/"),
    "garagenoord": ("Garage Noord", "https://www.garagenoord.com/club/9-lives-of-garage-noord"),
    "skatecafe": ("Skatecafe Karin & Yvonne", "https://skatecafe.weticket.io/"),
    "deceuvel": ("De Ceuvel", "https://deceuvel.nl/en/events/"),
    "radar": ("radar.squat.net", "https://radar.squat.net/en/events/city/Amsterdam"),
    "delamar": ("DeLaMar", "https://delamar.nl/en/"),
    "nieuweanita": ("De Nieuwe Anita", "https://denieuweanita.nl/agenda/"),
    "verzetsmuseum": ("Verzetsmuseum", "https://www.verzetsmuseum.org/"),
    "wereldmuseum": ("Wereldmuseum", "https://amsterdam.wereldmuseum.nl/"),
    "odessa": ("Odessa", "https://www.odessa.amsterdam/"),
    "ot301": ("OT301", "https://ot301.nl/agenda"),
    "cavia": ("Filmhuis Cavia", "https://www.filmhuiscavia.nl/"),
    "cinetol": ("Cinetol", "https://www.cinetol.nl/programma"),
    "ccamstel": ("CC Amstel", "https://ccamstel.nl/programma"),
    "volkshotel": ("Volkshotel", "https://www.volkshotel.nl/en/agenda/"),
    "wethepeople": ("We The People", "https://www.wethepeopleamsterdam.nl/"),
    "dezwijger": ("Pakhuis de Zwijger", "https://dezwijger.nl/agenda"),
    "lab111": ("LAB111", "https://www.lab111.nl/programma/"),
    "tolhuistuin": ("Tolhuistuin", "https://tolhuistuin.nl/en/agenda"),
    "iamsterdam": ("I amsterdam Uitagenda", "https://www.iamsterdam.com/uit/agenda"),
    "artis": ("ARTIS-Micropia", "https://www.artis.nl/nl/artis-micropia"),
    "schooloflife": ("The School of Life", "https://www.theschooloflife.com/amsterdam/agenda/"),
    "offlineclub": ("The Offline Club", "https://www.theoffline-club.com/city-chapters/amsterdam-chapter"),
}
NOTES = {"delamar": "dates load in their ticket app – check site", "artis": "no dated events, daily programme",
         "wethepeople": "check site for next event", "offlineclub": "calendar is a widget – check site",
         "vondelbunker": "included via radar.squat.net"}

NL = set("de het een en van voor met over wat hoe waarom jouw je jij niet ook naar uit bij als wordt worden zijn onze ons wij we leer leren samen avond middag lezing gesprek voorstelling kinderen jeugd verhaal nieuwe zonder tegen door dan kan maar deze dit welkom spreekuur buurt".split())
EN = set("the and of for with about what how why your you not to from at is are our we learn together evening night talk english".split())
PROTEST = re.compile(r"\b(protest\w*|demonstratie\w*|demonstration\w*|vigil|betoging\w*|vlaggen voor)\b", re.I)

# Last-chance classifier for events a source left as "other": venue first, then keywords in title and blurb.
VENUE_CAT = [("de trut","club"),("paradiso","music"),("melkweg","music"),("de balie","talk"),("pakhuis de zwijger","talk"),("nieuwland","workshop"),("rapenburg 51","workshop"),("de hallen","community"),("molli chaoot","community"),("huis vrederiks","community"),("occii","music"),("joe's garage","music"),("griffioen","music"),("zaal 100","music"),("de nieuwe anita","community"),("verzetsmuseum","community"),("de ceuvel","community"),("lag","community"),("podium mozaïek","theatre"),("spui25","talk"),("ot301","music"),("volkshotel","community"),("camping","community"),("museumplein","community")]
WORD_CAT = [
    ("club", r"\b(party|techno|rave|dj set|club night|house night|disco|clubnacht|afterparty|dance floor)\b"),
    ("music", r"\b(concert|live music|beats|gig|band|jam session|jazz|choir|koor|sessie|session|album|DJ|festival)\b"),
    ("workshop", r"\b(workshop|course|cursus|yoga|workout|class|training|massage|treatment|meditation|circle|lesson|les|learn)\b"),
    ("talk", r"\b(book club|talk|lecture|lezing|debate|debat|gesprek|discussion|presentation|panel|conversation|book launch|boekpresentatie|kennismakers|politics|cafe)\b"),
    ("theatre", r"\b(theatre|theater|comedy|cabaret|show|performance|voorstelling|quiz|popquiz|open mic|stand-up|dance)\b"),
    ("community", r"\b(market|markt|yard sale|dinner|diner|lunch|chef|taalcafé|speed|meet|swap|repair|exhibition|expositie|tentoonstelling|opening|gallery|art)\b"),
]
def classify_other(e):
    ven = (e.get("v") or "").lower()
    txt = (e["t"] + " " + (e.get("b") or ""))
    for c, rx in WORD_CAT[:2]:                      # clear music words win over the venue
        if re.search(rx, e["t"], re.I): return c
    for k, c in VENUE_CAT:
        if k in ven: return c
    for c, rx in WORD_CAT:
        if re.search(rx, txt, re.I): return c
    return "other"
LANGCATS = {"talk", "theatre", "comedy", "workshop", "community", "kids", "other"}
DUTCH_VENUES = {"dezwijger", "schooloflife", "nieuweanita", "ccamstel", "verzetsmuseum"}

def clean(e):
    e["t"] = re.sub(r"\]?\s*\((?:/|https?://)[^)]*\)", "", e.get("t", "")).strip().rstrip("]").lstrip("[").strip()
    if e.get("v"): e["v"] = re.split(r"\*\*|\n", e["v"])[0].strip()
    if e.get("p") in ("€0", "€ 0", "€0,-", "0"): e["p"] = "Free"
    for k in list(e):
        if e[k] in (None, "", []): del e[k]
    return e

def run(key, fn, *args):
    try:
        cleaned = [clean(e) for e in fn(*args) if e.get("d") and e.get("t")]
        return [e for e in cleaned if re.search(r"\w", e.get("t", ""))]   # no empty or dash-only titles
    except Exception as ex:
        print(f"  !! parser {key} crashed: {ex}")
        return []

def collect(today):
    per = {}
    for key in MD_KEYS:
        f = os.path.join(DATA, f"{key}.md")
        if not os.path.exists(f): per[key] = []; continue
        per[key] = run(key, importlib.import_module(key).parse, open(f, errors="ignore").read(), today)
    cav = importlib.import_module("cavia"); per["cavia"] = []
    for f in sorted(glob.glob(os.path.join(DATA, "cavia_*.md"))):
        per["cavia"] += run("cavia", cav.parse, open(f, errors="ignore").read(), today)
    f = os.path.join(DATA, "cinetol.html")
    per["cinetol"] = run("cinetol", importlib.import_module("cinetol").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    f = os.path.join(DATA, "radar.json")
    per["radar"] = run("radar", importlib.import_module("radar").parse_api, json.load(open(f)).get("result", {}), today) if os.path.exists(f) else []
    pages = [open(p, errors="ignore").read() for p in sorted(glob.glob(os.path.join(DATA, "iamsterdam", "p*.html")))]
    per["iamsterdam"] = run("iamsterdam", importlib.import_module("iamsterdam").parse_pages, pages, today)
    if not os.environ.get("NO_PAGE_TIMES"):
        try:
            import pagetimes
            pagetimes.enrich(per, today)
        except Exception as ex:
            print(f"  !! start-time lookup skipped: {ex}")
    return per

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())[:22]

def merge(per):
    order = {"iamsterdam": 3, "radar": 2, "amsterdamalternative": 1, "offbeat": 1}
    allev = [e for k in per for e in per[k]]
    for e in allev:
        v = e.get("v", "")
        if e["s"] == "ot301" and v and not v.startswith("OT301"): e["v"] = f"OT301 · {v}"
        elif e["s"] == "volkshotel" and v and v != "Volkshotel": e["v"] = f"Volkshotel · {v}"
        elif e["s"] == "deceuvel": e["v"] = "De Ceuvel"
        e["v"] = re.sub(r"^OT301-", "OT301 · ", e.get("v", ""))
        if re.fullmatch(r"(?i)de nieuwe anita", e["v"]): e["v"] = "De Nieuwe Anita"
    allev.sort(key=lambda e: order.get(e["s"], 0))
    seen, out = {}, []
    for e in allev:
        k = (e["d"], norm(e["t"]))
        if k in seen and seen[k]["s"] != e["s"]:
            s0 = seen[k]; a = s0.setdefault("a", [])
            if e["s"] not in a: a.append(e["s"])
            if e.get("nl"): s0["nl"] = 1
            continue
        seen.setdefault(k, e); out.append(e)
    for e in out:
        if e.get("c") in ("other", None, ""): e["c"] = classify_other(e)
    for e in out:
        if e.get("c") in ("community", "talk", "other", "kids") and PROTEST.search(e["t"]): e["c"] = "protest"
    for e in out:
        if e.get("nl") or e.pop("en", None) or e.get("c") not in LANGCATS: continue
        words = re.findall(r"[a-zà-ÿ']+", (e["t"] + " " + e.get("b", "")).lower())
        n = sum(w in NL for w in words); en = sum(w in EN for w in words)
        if (e["s"] in DUTCH_VENUES and en == 0 and n >= 1) or (n >= 2 and n > en): e["nl"] = 1
    out.sort(key=lambda e: (e["d"], e.get("h") or "99"))
    return out

def load_previous(path_or_url):
    """Events from the last published events.json (file path or URL)."""
    try:
        if path_or_url.startswith("http"):
            import subprocess
            r = subprocess.run(["curl", "-sS", "-f", "-m", "60", path_or_url], capture_output=True, text=True)
            return json.loads(r.stdout).get("events", [])
        return json.load(open(path_or_url)).get("events", [])
    except Exception:
        return []

def main():
    """python3 build.py [--out public] [--previous URL-or-path-of-events.json]"""
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(HERE, "public")
    prev = sys.argv[sys.argv.index("--previous") + 1] if "--previous" in sys.argv else None
    os.makedirs(out, exist_ok=True)
    today = datetime.date.today()
    per = collect(today)
    previous = load_previous(prev) if prev else []
    old = {}
    for e in previous: old[e["s"]] = old.get(e["s"], 0) + 1
    # A source that broke or was blocked this run keeps its last good events (future ones only)
    kept = []
    for k, evs in per.items():
        if not evs and old.get(k):
            per[k] = [e for e in previous if e["s"] == k and (e.get("ed") or e["d"]) >= today.isoformat()]
            for e in per[k]:
                for f in ("la", "lo", "ar", "a"): e.pop(f, None)
            kept.append(k)
    events = merge(per)
    import geo
    looked = geo.enrich(events)
    src = {k: {"name": n, "url": u, "agg": k in AGG, **({"note": NOTES[k]} if k in NOTES else {})} for k, (n, u) in SOURCES.items()}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    json.dump({"updated": stamp, "events": events, "sources": src}, open(os.path.join(out, "events.json"), "w"),
              ensure_ascii=False, separators=(",", ":"))
    open(os.path.join(out, "index.html"), "w").write(open(os.path.join(HERE, "template.html")).read().replace("__CONTACT__", os.environ.get("CONTACT_EMAIL", "")))

    final = {}
    for e in events: final[e["s"]] = final.get(e["s"], 0) + 1
    print(f"{'source':22} parsed  on site  previous")
    warn = []
    for k in sorted(per):
        n, o = len(per[k]), old.get(k)
        flag = "  <-- kept previous data" if k in kept else ""
        if not flag and n == 0: flag = "  <-- nothing parsed"
        elif not flag and o and n < o * 0.4: flag = "  <-- big drop"
        if flag: warn.append(k)
        print(f"{k:22} {n:6} {final.get(k,0):8} {o if o is not None else '-':>9}{flag}")
    placed = sum(1 for e in events if e.get("la")); areas = sum(1 for e in events if e.get("ar"))
    print(f"\n{len(events)} events, {placed} on the map, {areas} with an area; {looked} new venue lookups")
    if warn: print("Check these sources:", ", ".join(warn))

if __name__ == "__main__":
    main()
