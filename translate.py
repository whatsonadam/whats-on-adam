"""Translate Dutch event titles and descriptions into English, once per text.

Only events that a parser marks with "tl": 1 are touched. That is the protest and activism sources, where the
language of the source should not keep people away. Results are saved in translations.json, so every text uses
DeepL's free quota once. Without a DEEPL_API_KEY (GitHub repository secret), or when DeepL is down or over quota,
the original text simply stays and nothing else breaks.

The original title is kept in "to" whenever it was translated.
"""
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "translations.json")
MAX_CHARS = int(os.environ.get("TRANSLATE_MAX_CHARS", "30000"))   # per run, far below the free 500,000 a month
BATCH = 40
UA = "whatsonadam-agenda (non-commercial hobby site; github.com/whatsonadam/whats-on-adam)"


def _load():
    try:
        return json.load(open(CACHE))
    except Exception:
        return {}


def _save(cache):
    json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0, sort_keys=True)


def _call(key, texts):
    """One DeepL request. Free keys end in ':fx' and use the api-free host."""
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    req = urllib.request.Request(
        f"https://{host}/v2/translate",
        data=json.dumps({"text": texts, "target_lang": "EN-GB"}).encode(),
        headers={"Authorization": f"DeepL-Auth-Key {key}", "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [t["text"] for t in json.load(r)["translations"]]


def enrich(events, call=_call):
    """Replace Dutch title and description with English on events marked tl=1. Returns how many texts were newly translated."""
    flagged = [e for e in events if e.pop("tl", None)]
    if not flagged:
        return 0
    cache = _load()
    key = os.environ.get("DEEPL_API_KEY", "").strip()
    need = []
    for e in flagged:
        for f in ("t", "b"):
            s = e.get(f)
            if s and s not in cache and s not in need:
                need.append(s)
    done = 0
    if need and not key:
        print(f"  translation skipped: no DEEPL_API_KEY, {len(need)} texts stay as the source wrote them")
    elif need:
        budget = MAX_CHARS
        i = 0
        while i < len(need) and budget > 0:
            batch, used = [], 0
            while i < len(need) and len(batch) < BATCH and used + len(need[i]) <= budget:
                batch.append(need[i]); used += len(need[i]); i += 1
            if not batch:
                break
            try:
                out = call(key, batch)
            except Exception as ex:
                print(f"  !! translation stopped ({str(ex)[:80]}); the rest stay as the source wrote them")
                break
            if len(out) != len(batch):
                print("  !! translation returned an unexpected result; skipped")
                break
            for s, t in zip(batch, out):
                cache[s] = t
            budget -= used
            done += len(batch)
        if done:
            _save(cache)
    for e in flagged:
        for f in ("t", "b"):
            s = e.get(f)
            t = cache.get(s) if s else None
            if t and t != s:
                if f == "t":
                    e["to"] = s
                e[f] = t
    return done
