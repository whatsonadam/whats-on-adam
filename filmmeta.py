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
MAX_LOOKUPS = int(os.environ.get("FILMMETA_MAX", "400"))
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
                return {"yr": a["releaseYear"], "du": a["duration"], "dr": ", ".join((a.get("directors") or [])[:2])}
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
            return {"yr": int(yr), "du": d["runtime"], "dr": ", ".join(dirs)}
        time.sleep(0.25)
    return None


def enrich(events, today):
    try: cache = json.load(open(CACHE))
    except Exception: cache = {}
    key = os.environ.get("TMDB_API_KEY", "").strip()
    now = today.isoformat()
    todo, seen = [], set()
    for e in events:
        if e.get("c") != "film" or e.get("yr"): continue
        k = norm(e["t"])
        c = cache.get(k)
        if c and c.get("yr"): continue
        if c and (today - datetime.date.fromisoformat(c.get("tried", now))).days < RETRY_AFTER_DAYS and bool(c.get("tmdb")) == bool(key): continue
        if k not in seen: seen.add(k); todo.append((k, e["t"]))
    done = 0
    for k, title in todo[:MAX_LOOKUPS]:
        m = from_cineville(title) or (from_tmdb(title, key) if key else None)
        cache[k] = {**(m or {}), "tried": now, "tmdb": bool(key)}
        done += 1
        time.sleep(0.25)
    for e in events:
        if e.get("c") == "film" and not e.get("yr"):
            c = cache.get(norm(e["t"]))
            if c and c.get("yr"):
                e["yr"], e["du"] = c["yr"], c["du"]
                if c.get("dr"): e["dr"] = c["dr"]
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0, sort_keys=True)
    films = [e for e in events if e.get("c") == "film"]
    print(f"film info: {sum(1 for e in films if e.get('yr'))} of {len(films)} screenings have year and length "
          f"({done} new titles looked up, {max(0, len(todo) - done)} left for next run, TMDB {'on' if key else 'off'})")
