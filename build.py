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

CINEMA_KEYS = ["eye", "rialto", "uitkijk", "themovies", "studiok", "ketelhuis", "hyena", "filmhallen", "cinecenter",
               "melkwegcinema", "amstelveen", "devlugt", "thepulse", "omval", "docpaviljoen", "kriterion", "filmladder"]
AGG = {"radar", "offbeat", "amsterdamalternative", "iamsterdam", "luma"}
# Page keys whose markdown feeds a parser of the same name
MD_KEYS = ["mezrab", "vrankrijk", "aralez", "desering", "amsterdamalternative", "offbeat", "likeminds",
           "garagenoord", "skatecafe", "deceuvel", "nieuweanita", "verzetsmuseum", "wereldmuseum", "odessa",
           "ot301", "ccamstel", "volkshotel", "lab111", "tolhuistuin", "dezwijger", "schooloflife",
           "verbroederij", "radion", "parallel", "opsolder", "grachten", "dehallen", "waterkant", "brecht", "iisg",
           "frascati", "amsterdammuseum", "marineterrein", "tanker", "prik", "theaternl"]

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
    "eye": ("Eye Filmmuseum", "https://www.eyefilm.nl/en/whats-on"),
    "rialto": ("Rialto", "https://depijp.rialtofilm.nl/nl/agenda"),
    "uitkijk": ("De Uitkijk", "https://www.uitkijk.nl/"),
    "themovies": ("The Movies", "https://themovies.nl/"),
    "studiok": ("Studio/K", "https://studio-k.nu/"),
    "ketelhuis": ("Het Ketelhuis", "https://www.ketelhuis.nl/"),
    "hyena": ("FC Hyena", "https://fchyena.nl/"),
    "filmhallen": ("Filmhallen", "https://filmhallen.nl/"),
    "cinecenter": ("Cinecenter", "https://www.cinecenter.nl/programma"),
    "melkwegcinema": ("Melkweg Cinema", "https://www.melkweg.nl/nl/agenda"),
    "amstelveen": ("Cinema Amstelveen", "https://www.cineville.nl/"),
    "devlugt": ("Cinema De Vlugt", "https://www.cineville.nl/"),
    "thepulse": ("Cinema The Pulse", "https://www.cineville.nl/"),
    "omval": ("De Omval", "https://www.cineville.nl/"),
    "docpaviljoen": ("Het Documentaire Paviljoen", "https://www.idfa.nl/vondelpark/agenda-het-documentaire-paviljoen"),
    "kriterion": ("Kriterion", "https://www.cineville.nl/nl-NL/theaters/kriterion"),
    "filmladder": ("Pathé and Vue (via Filmladder)", "https://www.filmladder.nl/amsterdam/bioscopen"),
    "ade": ("Amsterdam Dance Event", "https://www.amsterdam-dance-event.nl/en/program/"),
    "tolhuistuin": ("Tolhuistuin", "https://tolhuistuin.nl/en/agenda"),
    "iamsterdam": ("I amsterdam Uitagenda", "https://www.iamsterdam.com/uit/agenda"),
    "artis": ("ARTIS-Micropia", "https://www.artis.nl/nl/artis-micropia"),
    "schooloflife": ("The School of Life", "https://www.theschooloflife.com/amsterdam/agenda/"),
    "offlineclub": ("The Offline Club", "https://luma.com/theofflineclubamsterdam"),
    "luma": ("Luma Amsterdam", "https://luma.com/amsterdam"),
    "ra": ("Resident Advisor", "https://ra.co/events/nl/amsterdam"),
    "verbroederij": ("De VerbroederIJ", "https://deverbroederij.nl/"),
    "ruigoord": ("Ruigoord", "https://ruigoord.nl/programma/"),
    "radion": ("RADION", "https://radion.amsterdam/program"),
    "parallel": ("Parallel", "https://parallel.am/"),
    "opsolder": ("Museum Ons' Lieve Heer op Solder", "https://opsolder.nl/agenda/"),
    "grachten": ("Museum of the Canals", "https://grachten.museum/en/temporary-exhibitions/"),
    "dehallen": ("De Hallen", "https://www.dehallen-amsterdam.nl/en/agenda"),
    "waterkant": ("Waterkant", "https://www.waterkantamsterdam.nl/agenda"),
    "brecht": ("Café Brecht", "https://www.cafebrecht.nl/agenda"),
    "iisg": ("IISG", "https://iisg.amsterdam/nl/events"),
    "frascati": ("Frascati", "https://www.frascatitheater.nl/nl/agenda"),
    "amsterdammuseum": ("Amsterdam Museum", "https://www.amsterdammuseum.nl/en/see-and-do/agenda"),
    "marineterrein": ("Marineterrein", "https://www.marineterrein.nl/agenda"),
    "tanker": ("De Roze Tanker", "https://www.detanker.nl/agenda"),
    "prik": ("Prik", "https://www.prikamsterdam.nl"),
    "theaternl": ("Theater.nl (Nationale Opera & Ballet)", "https://www.theater.nl/voorstellingen/opera/amsterdam"),
    "iamsterdamballet": ("I amsterdam (Dutch National Ballet nights)", "https://www.iamsterdam.com/en/whats-on/calendar/theatre-and-stage/stage/dutch-national-opera-and-ballet"),
    "weekly": ("Weekly nights (entered by hand)", "https://github.com/whatsonadam/whats-on-adam/blob/main/parsers/weekly.py"),
    "watkanikdoen": ("Wat kan ik doen?", "https://watkanikdoen.nl/acties"),
    "rightsforum": ("The Rights Forum", "https://rightsforum.org/agenda/"),
    "xr": ("Extinction Rebellion NL", "https://extinctionrebellion.nl/events/"),
    "socialisme": ("socialisme.nu agenda", "https://socialisme.nu/agenda/"),
}
NOTES = {"filmladder": "big chains, a week ahead; hidden in the Cinema tab until you tick the box","kriterion": "via Cineville, only a week or two ahead", "artis": "no dated events, daily programme",
         "wethepeople": "check site for next event",         "vondelbunker": "included via radar.squat.net",
         "weekly": "Jazz Café Alto, MKZ, De Trut, Robin Food Kollektief and The Queen's Head: standing nights from each venue's site, check before you go",
         "watkanikdoen": "national protest agenda, Amsterdam actions only, translated to English",
         "rightsforum": "national Palestine actions agenda, Amsterdam only, translated to English",
         "xr": "national agenda, Amsterdam events only, translated to English",
         "socialisme": "national agenda, Amsterdam entries only, translated to English"}

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

def _load_json(path):
    try: return json.load(open(path))
    except Exception: return None

def collect(today):
    per = {}
    for key in MD_KEYS:
        f = os.path.join(DATA, f"{key}.md")
        if not os.path.exists(f): per[key] = []; continue
        per[key] = run(key, importlib.import_module(key).parse, open(f, errors="ignore").read(), today)
    f = os.path.join(DATA, "ruigoord.ics")
    per["ruigoord"] = run("ruigoord", importlib.import_module("ruigoord").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    per["weekly"] = run("weekly", importlib.import_module("weekly").parse, "", today)   # standing nights entered by hand
    cav = importlib.import_module("cavia"); per["cavia"] = []
    for f in sorted(glob.glob(os.path.join(DATA, "cavia_*.md"))):
        per["cavia"] += run("cavia", cav.parse, open(f, errors="ignore").read(), today)
    f = os.path.join(DATA, "cinetol.html")
    per["cinetol"] = run("cinetol", importlib.import_module("cinetol").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    f = os.path.join(DATA, "radar.json")
    radar = {}
    try: radar = json.load(open(f)).get("result", {}) if os.path.exists(f) else {}
    except Exception as ex: print(f"  !! radar.json unreadable ({ex}); keeping the previous radar events")
    per["radar"] = run("radar", importlib.import_module("radar").parse_api, radar, today) if radar else []
    for key in CINEMA_KEYS:
        f = os.path.join(DATA, f"{key}.cin")
        per[key] = run(key, importlib.import_module(key).parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    ade_pages = []
    for p in sorted(glob.glob(os.path.join(DATA, "ade", "p*.json"))):
        try: ade_pages.append(json.load(open(p)))
        except Exception: pass
    per["ade"] = run("ade", importlib.import_module("ade").parse_pages, ade_pages, today)
    ra_pages = []
    for p in sorted(glob.glob(os.path.join(DATA, "ra", "p*.json"))):
        try: ra_pages.append(json.load(open(p)))
        except Exception: pass
    per["ra"] = run("ra", importlib.import_module("ra").parse_pages, ra_pages, today)
    dl = [("https://delamar.nl/voorstellingen/" + os.path.basename(p)[:-5] + "/", open(p, errors="ignore").read())
          for p in sorted(glob.glob(os.path.join(DATA, "delamar", "*.html")))]
    per["delamar"] = run("delamar", importlib.import_module("delamar").parse_pages, dl, today)
    f = os.path.join(DATA, "offlineclub.html")
    per["offlineclub"] = run("offlineclub", importlib.import_module("offlineclub").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    f = os.path.join(DATA, "luma.json")
    per["luma"] = run("luma", importlib.import_module("luma").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    f = os.path.join(DATA, "socialisme.html")
    per["socialisme"] = run("socialisme", importlib.import_module("socialisme").parse, open(f, errors="ignore").read(), today) if os.path.exists(f) else []
    rf = [open(p, errors="ignore").read() for p in sorted(glob.glob(os.path.join(DATA, "rightsforum", "p*.html")))]
    per["rightsforum"] = run("rightsforum", importlib.import_module("rightsforum").parse_pages, rf, today) if rf else []
    xr_pages = [open(p, errors="ignore").read() for p in sorted(glob.glob(os.path.join(DATA, "xr", "p*.html")))]
    xr_det = {os.path.basename(p)[:-5]: open(p, errors="ignore").read() for p in glob.glob(os.path.join(DATA, "xr", "detail", "*.html"))}
    per["xr"] = run("xr", importlib.import_module("xr").parse_pages, xr_pages, xr_det, today) if xr_pages else []
    wk_pages = [j for j in (_load_json(p) for p in sorted(glob.glob(os.path.join(DATA, "watkanikdoen", "p*.json")))) if j]
    wk_det = {os.path.basename(p)[:-5]: _load_json(p) for p in glob.glob(os.path.join(DATA, "watkanikdoen", "detail", "*.json"))}
    per["watkanikdoen"] = run("watkanikdoen", importlib.import_module("watkanikdoen").parse_pages, wk_pages, {k: v for k, v in wk_det.items() if v}, today) if wk_pages else []
    pages = [open(p, errors="ignore").read() for p in sorted(glob.glob(os.path.join(DATA, "iamsterdam", "p*.html")))]
    per["iamsterdam"] = run("iamsterdam", importlib.import_module("iamsterdam").parse_pages, pages, today)
    bl = {os.path.basename(p)[:-5]: open(p, errors="ignore").read() for p in glob.glob(os.path.join(DATA, "iamsterdam_ballet", "*.html"))}
    per["iamsterdamballet"] = run("iamsterdamballet", importlib.import_module("iamsterdamballet").parse_pages, {"/uit/agenda/voorstellingen/theater-en-podiumkunsten/" + k: v for k, v in bl.items()}, today) if bl else []
    if not os.environ.get("NO_PAGE_TIMES"):
        try:
            import pagetimes
            pagetimes.enrich(per, today)
        except Exception as ex:
            print(f"  !! start-time lookup skipped: {ex}")
    try:   # one consistent look for prices that parsers wrote ("€18.00", "donation", "Sold out" ...)
        from _price import tidy
        for evs in per.values():
            for e in evs:
                if e.get("p"):
                    e["p"], sold = tidy(e["p"])
                    if sold:
                        e["so"] = True
                    if not e["p"]:
                        del e["p"]
    except Exception as ex:
        print(f"  !! price tidy skipped: {ex}")
    if not os.environ.get("NO_PAGE_PRICES"):
        try:
            import pageprices
            st = pageprices.fill([e for evs in per.values() for e in evs], today)
            print(f"  prices from event pages: {st['applied']} events priced from cache, {st['fetched']} pages read, "
                  f"{st['found']} with a price, {st['unreadable']} unreadable, {st['wanted']} pages wanted in total")
            for src, x in sorted(st["by_source"].items()):
                print(f"    {src:16} read {x['read']:4}  price {x['price']:4}  unreadable {x['unreadable']:3}")
        except Exception as ex:
            print(f"  !! page price lookup skipped: {ex}")
    return per

def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())[:22]

# Words that say nothing about which event it is, ignored when comparing titles across sources
TITLE_NOISE = set("ade amsterdam dance event special the a de het een van pres presents x w with at in met bij live 2025 2026".split())
def title_words(t): return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in TITLE_NOISE and len(w) > 1}
def same_event(t1, t2):
    """Clearly the same event: one title's words all appear in the other ('Malugi' and 'Malugi - ADE')."""
    a, b = title_words(t1), title_words(t2)
    if not a or not b: return False
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    if not small <= big: return False
    return len(small) > 1 or len(next(iter(small))) >= 4

def merge_doubles(out):
    """Same date, start time and venue plus clearly the same title = one event listed twice."""
    groups, keep, merged = {}, [], 0
    for e in out:
        if e.get("c") == "film" or not e.get("h") or not e.get("v"): keep.append(e); continue
        k = (e["d"], e["h"], norm(e["v"])[:8])
        hit = next((x for x in groups.get(k, []) if same_event(x["t"], e["t"])), None)
        if hit:
            if e["s"] != hit["s"]:
                a = hit.setdefault("a", [])
                if e["s"] not in a: a.append(e["s"])
            if e.get("nl"): hit["nl"] = 1
            merged += 1
            continue
        groups.setdefault(k, []).append(e); keep.append(e)
    if merged: print(f"  merged {merged} double listings (same date, time, venue, clearly the same title)")
    return keep

STRONG_PROTEST = re.compile(r"\b(demonstratie\w*|demonstration\w*|betoging\w*|vigil|flitsactie\w*|vlaggen voor)\b", re.I)
ACTION = re.compile(r"\b(wake|demonstrat\w*|protest\w*|betoging\w*|mars|march|actie\w*|action\w*|vigil|rode lijn|red line|blokkade\w*|sit-?in)\b", re.I)
NOT_PROTEST = [(re.compile(r"\b(%s)\b" % w, re.I), c) for w, c in [
    (r"lezing\w*|lecture\w*|vertoning\w*|documentaire\w*|screening\w*|film\w*|boekpresentatie\w*|boek\w*|book\w*|debat\w*|debate|gesprek\w*|discussie\w*|panel|talk|science fiction\w*|marxism|marxisme|presentation|presentatie", "talk"),
    (r"workshop\w*|training\w*|cursus\w*|course|leerkring", "workshop"),
    (r"community night|dinner|diner|eten|borrel|potluck|spreekuur|woonspreekuur|bijeenkomst|meetup|social", "community")]]
PROTEST_NOISE = set("de het een en van voor in op met tegen naar te the of and for to a at amsterdam protest protests demonstratie demonstration actie action mars march nieuw nieuwe geen enkele".split())

def merge_protests(out):
    """The same protest often comes from two agendas with differently worded titles ('De rode lijn voorbij' and
    'Rode lijn: geen enkele steun voor genocide!'). Same day, protest category and at least two shared meaningful
    title words = one event. The listing with a start time, then the longer description, is kept."""
    def words(t): return {w for w in re.findall(r"[a-zà-ÿ0-9]+", t.lower()) if len(w) > 2 and w not in PROTEST_NOISE}
    def mins(h): return int(h[:2]) * 60 + int(h[3:5])
    def apart(a, b): return bool(a.get("h") and b.get("h") and abs(mins(a["h"]) - mins(b["h"])) >= 60)   # a service before the march is its own event
    keep, by_day, merged = [], {}, 0
    for e in out:
        if e.get("c") != "protest": keep.append(e); continue
        w = words(e["t"])
        hit = next((x for x, xw in by_day.get(e["d"], []) if len(w & xw) >= 2 and not apart(e, x)), None)
        if hit is None:
            by_day.setdefault(e["d"], []).append((e, w)); keep.append(e); continue
        merged += 1
        for f in ("h", "eh"):
            if e.get(f) and not hit.get(f): hit[f] = e[f]
        if len(e.get("b", "")) > len(hit.get("b", "")): hit["b"] = e["b"]
        if len(e.get("v", "")) > len(hit.get("v", "")) and "amsterdam" in e.get("v", "").lower(): hit["v"] = e["v"]
        if e["s"] != hit["s"]:
            a = hit.setdefault("a", [])
            if e["s"] not in a: a.append(e["s"])
    if merged: print(f"  merged {merged} protests listed by more than one agenda")
    return keep

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
        k = (e["d"], norm(e["t"])) if e.get("c") != "film" else (e["d"], norm(e["t"]), norm(e.get("v", ""))[:10], e.get("h") or "")
        if k in seen and seen[k]["s"] != e["s"]:
            s0 = seen[k]; a = s0.setdefault("a", [])
            if e["s"] not in a: a.append(e["s"])
            if e.get("nl"): s0["nl"] = 1
            continue
        seen.setdefault(k, e); out.append(e)
    out = merge_doubles(out)
    for e in out:                                   # films: English signals in the title when the cinema gives no language data
        if e.get("c") == "film" and not e.get("ef") and not e.get("nl") and re.search(r"eng(?:lish)?\.? ?subs?|english sub|\bOV\b|english spoken", e["t"], re.I): e["ef"] = 1
        if e.get("c") == "film" and not e.get("sb") and re.search(r"eng(?:lish)?\.? ?subs?|english sub", e["t"], re.I): e["sb"] = ["en"]
    for e in out:
        if e.get("c") in ("other", None, ""): e["c"] = classify_other(e)
    for e in out:
        if e.get("c") in ("community", "talk", "other", "kids") and PROTEST.search(e["t"]) and not (e["c"] == "talk" and any(rx.search(e["t"]) for rx, _ in NOT_PROTEST)): e["c"] = "protest"
    for e in out:                                   # the activism agendas also list lectures, films, dinners: only real actions stay Protest
        if e.get("c") == "protest" and not STRONG_PROTEST.search(e["t"]):
            for rx, cat in NOT_PROTEST:
                if rx.search(e["t"]): e["c"] = cat; break
            else:
                if e.get("s") == "rightsforum" and not ACTION.search(e["t"]): e["c"] = "talk"   # its agenda mixes in events with no action word
    for e in out:
        if e.get("c") == "protest": e.pop("nl", None)    # protests are never hidden by the English-friendly filter
    out = merge_protests(out)
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
    try:
        import translate
        translated = translate.enrich(events)
        if translated: print(f"  translated {translated} protest texts to English")
    except Exception as ex: print(f"  !! translation failed ({ex}); continuing with the original text")
    try:
        import filmmeta
        filmmeta.enrich(events, today)
    except Exception as ex: print(f"  !! film info lookup failed ({ex}); continuing without it")
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
