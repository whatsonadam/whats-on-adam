"""Fill in year, length and director for films that don't carry them yet, once per film title.

Order of lookups for each new title (results, including "not found", are saved in filmmeta.json so
later runs only look up new titles):
  1. Cineville's public film database (no key needed).
  2. The Movie Database (TMDB), only when a TMDB_API_KEY is set in the GitHub repository secrets.
Only an exact title match is accepted, so a wrong film is never attached.
Politeness: one request at a time, a pause between requests, at most MAX_LOOKUPS titles per run.
"""
import datetime, json, os, re, subprocess, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "filmmeta.json")
MAX_LOOKUPS = int(os.environ.get("FILMMETA_MAX", "500"))
RETRY_AFTER_DAYS = 14
CINEVILLE = "https://api.cineville.nl/productions/search"
UA = "whatsonadam-agenda (non-commercial hobby site; github.com/whatsonadam/whats-on-adam)"


def norm(t):
    t = re.sub(r"&#\d+;|&\w+;", " ", t.lower())
    return re.sub(r"[^\w]+", " ", t).strip()


def variants(t):
    """The title as shown, then progressively cleaner guesses at the real film title."""
    t = t.replace("&#8217;", "’").replace("&#8211;", "-").replace("&amp;", "&")
    v = [t]
    t2 = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", t).strip()
    v.append(t2)
    t3 = re.split(r"\s+[|–—]\s+|\s+-\s+", t2)[0].strip()
    v.append(t3)
    t4 = re.sub(r"(?i)^(eng(lish)? subs?|ov)\s*:\s*", "", t3)
    v.append(t4)
    v.append(re.sub(r"(?i)\s+incl\..*$", "", re.sub(r"(?i)^.*?\bpresents\s+", "", t4)))
    if ": " in t4 and re.match(r"(?i)(imagine film festival|cine of the times|aade|ade|cinemini|cinebaby|ff)\b", t4):
        v.append(t4.split(": ", 1)[1])
    return list(dict.fromkeys(x.strip() for x in v if x and x.strip()))


def _post(url, body):
    r = subprocess.run(["curl", "-sS", "-m", "20", "-A", UA, "-X", "POST", "-H", "Content-Type: application/json",
                        "-d", json.dumps(body), url], capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {}


def _get(url, headers=()):
    cmd = ["curl", "-sS", "-m", "20", "-A", UA]
    for h in headers: cmd += ["-H", h]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {}


def from_cineville(title):
    for v in variants(title):
        d = _post(CINEVILLE, {"title": {"eq": v}, "page": {"limit": 5}})
        for p in (d.get("_embedded") or {}).get("productions", []):
            a = p.get("attributes") or {}
            if a.get("duration") and a.get("releaseYear"):
                return {"yr": a["releaseYear"], "du": a["duration"], "dr": ", ".join((a.get("directors") or [])[:2]),
                        "lg": sorted({str(x).lower().split("-")[0] for x in (a.get("spokenLanguages") or [])})[:3]}
        time.sleep(0.25)
    return None


def from_tmdb(title, key):
    hdr = [f"Authorization: Bearer {key}"] if len(key) > 40 else []
    q = "" if hdr else f"&api_key={key}"
    base = "https://api.themoviedb.org/3"
    for v in variants(title):
        s = _get(f"{base}/search/movie?query={urllib.parse.quote(v)}{q}", hdr)
        want = norm(v)
        hit = next((m for m in (s.get("results") or [])[:6] if want in (norm(m.get("title", "")), norm(m.get("original_title", "")))), None)
        if not hit: time.sleep(0.25); continue
        d = _get(f"{base}/movie/{hit['id']}?append_to_response=credits{q}", hdr)
        yr = (d.get("release_date") or "")[:4]
        dirs = [c["name"] for c in (d.get("credits") or {}).get("crew", []) if c.get("job") == "Director"][:2]
        if d.get("runtime") and yr:
            return {"yr": int(yr), "du": d["runtime"], "dr": ", ".join(dirs),
                    "lg": [l["iso_639_1"] for l in (d.get("spoken_languages") or []) if l.get("iso_639_1")][:3],
                    "gn": [g["name"] for g in (d.get("genres") or [])][:3],
                    **({"rt": round(d["vote_average"], 1)} if d.get("vote_count", 0) >= 20 and d.get("vote_average") else {}),
                    **({"sy": _short(d["overview"])} if d.get("overview") else {})}
        time.sleep(0.25)
    return None


def _short(t, n=210):
    t = " ".join(t.split())
    if len(t) <= n: return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


FIELDS = ("yr", "du", "dr", "lg", "gn", "rt", "sy")


def enrich(events, today):
    """Cache entry per normalized title: {yr, du, dr, lg, gn, tried, tmdb, v}. v=4 means fully looked up (tm4: TMDB checked, incl. rating and synopsis)."""
    try: cache = json.load(open(CACHE))
    except Exception: cache = {}
    key = os.environ.get("TMDB_API_KEY", "").strip()
    now = today.isoformat()
    todo, seen = [], set()
    for e in events:
        if e.get("c") != "film": continue
        k = norm(e["t"])
        if k in seen: continue
        c = cache.get(k)
        if c and c.get("v") == 4 and (c.get("tm4") or not key or c.get("tmdb")):
            if c.get("yr") or (today - datetime.date.fromisoformat(c.get("tried", now))).days < RETRY_AFTER_DAYS: continue
        seen.add(k); todo.append((k, e["t"]))
    done = 0
    for k, title in todo[:MAX_LOOKUPS]:
        c = dict(cache.get(k) or {})
        if not c.get("yr"):
            c.update(from_cineville(title) or {})
            time.sleep(0.25)
        if key and not c.get("tm4"):
            m = from_tmdb(title, key)
            if m:
                for f in FIELDS:
                    if m.get(f) and not c.get(f): c[f] = m[f]
        c.update({"tried": now, "tmdb": bool(key), "v": 4})
        if key: c["tm4"] = True
        cache[k] = c
        done += 1
    for e in events:
        if e.get("c") != "film": continue
        c = cache.get(norm(e["t"]))
        if not c: continue
        for f in FIELDS:
            if c.get(f) and not e.get(f): e[f] = c[f]
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0, sort_keys=True)
    films = [e for e in events if e.get("c") == "film"]
    print(f"film info: {sum(1 for e in films if e.get('yr'))} of {len(films)} screenings have year and length, "
          f"{sum(1 for e in films if e.get('gn'))} have genres, {sum(1 for e in films if e.get('rt'))} ratings, {sum(1 for e in films if e.get('sy'))} synopses ({done} titles looked up, {max(0, len(todo) - done)} left for next run, TMDB {'on' if key else 'off'})")
