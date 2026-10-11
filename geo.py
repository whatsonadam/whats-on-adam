"""Venue locations and Amsterdam districts.

venues.json is the cache: {venue name: {"lat":..,"lon":..,"area":..,"q":"how it was found"}}
or {"skip": true} for names that can't be placed (e.g. "Various locations").
New names are looked up with Photon (photon.komoot.io, OpenStreetMap data), at most
MAX_LOOKUPS per run and one request per second. You can fix a wrong entry by editing
venues.json by hand; the script never overwrites an existing entry.
"""
import json, os, re, subprocess, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
VENUES = os.path.join(HERE, "venues.json")
DISTRICTS = json.load(open(os.path.join(HERE, "districts.json")))
BBOX = (4.72, 52.27, 5.08, 52.43)  # lon/lat box around Amsterdam
MAX_LOOKUPS = 120
AREA_NAMES = {"Westpoort": "West", "Weesp": "Weesp"}
# I amsterdam / offbeat neighbourhood tags -> district, used when there are no coordinates
TAG_AREAS = {"centrum": "Centrum", "citycentre": "Centrum", "noord": "Noord", "zuid": "Zuid", "south": "Zuid",
             "west": "West", "oost": "Oost", "nieuwwest": "Nieuw-West", "zuidoost": "Zuidoost",
             "amsterdam-centrum": "Centrum", "amsterdam-noord": "Noord", "amsterdam-zuid": "Zuid",
             "amsterdam-west": "West", "amsterdam-oost": "Oost", "amsterdam-nieuw-west": "Nieuw-West",
             "amsterdam-zuidoost": "Zuidoost", "jordaan": "Centrum", "de pijp": "Zuid", "depijp": "Zuid"}
SKIP = re.compile(r"(?i)(diverse locaties|various locations|online|livestream|^amsterdam( \(various\))?$|op locatie|tba|n\.?n\.?b)")

def _inside(lon, lat, ring):
    c = False; j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi: c = not c
        j = i
    return c

def area_of(lat, lon):
    for d in DISTRICTS:
        for poly in d["polys"]:
            if _inside(lon, lat, poly[0]) and not any(_inside(lon, lat, h) for h in poly[1:]):
                return AREA_NAMES.get(d["name"], d["name"])
    return None

def base_name(v):
    return re.split(r"\s+·\s+", v)[0].strip()

def _norm(s):
    return set(re.findall(r"[a-z0-9]{3,}", s.lower())) - {"amsterdam", "the", "het", "theater", "zaal"}

def _photon(q):
    url = "https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": q, "limit": 3, "bbox": ",".join(map(str, BBOX))})
    r = subprocess.run(["curl", "-sS", "-m", "20", "-A", "amsterdam-agenda (hobby site)", url], capture_output=True, text=True)
    try: return json.loads(r.stdout).get("features", [])
    except Exception: return []

def lookup(name, addr=None):
    """Return {"lat","lon","q"} or None. Prefer an address when the source gave one."""
    tries = []
    if addr: tries.append(("addr", f"{addr}, Amsterdam"))
    tries.append(("name", f"{name} Amsterdam"))
    want = _norm(name)
    for how, q in tries:
        feats = _photon(q); time.sleep(1.1)
        for f in feats:
            lon, lat = f["geometry"]["coordinates"]
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]): continue
            p = f["properties"]
            if how == "name":
                # only accept a place whose own name shares a real word with the venue name
                if not want or not (want & _norm(p.get("name", ""))): continue
            return {"lat": round(lat, 5), "lon": round(lon, 5), "q": how}
    return None

def load():
    try: return json.load(open(VENUES))
    except Exception: return {}

def save(v):
    json.dump(dict(sorted(v.items())), open(VENUES, "w"), ensure_ascii=False, indent=0)

def enrich(events):
    """Add lat/lon/area ('la','lo','ar') to events in place; look up unknown venues."""
    venues = load(); looked = 0
    addr_hint = {}
    for e in events:
        if e.get("addr"): addr_hint.setdefault(base_name(e["v"]), e["addr"])
    names = sorted({base_name(e["v"]) for e in events if e.get("v")}, key=lambda n: -sum(1 for e in events if base_name(e.get("v", "")) == n))
    for n in names:
        if n in venues: continue
        if SKIP.search(n): venues[n] = {"skip": True}; continue
        if looked >= MAX_LOOKUPS: break
        looked += 1
        hit = lookup(n, addr_hint.get(n))
        if hit:
            hit["area"] = area_of(hit["lat"], hit["lon"]); venues[n] = hit
        else:
            venues[n] = {"skip": True, "q": "not found"}
    save(venues)
    for e in events:
        info = venues.get(base_name(e.get("v", "")), {})
        if info.get("lat"):
            e["la"], e["lo"] = info["lat"], info["lon"]
            if info.get("area"): e["ar"] = info["area"]
        if "ar" not in e:
            for t in e.pop("tags", []) or []:
                if t in TAG_AREAS: e["ar"] = TAG_AREAS[t]; break
        e.pop("tags", None); e.pop("addr", None)
    return looked
