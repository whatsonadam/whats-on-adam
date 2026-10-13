"""Eye Filmmuseum parser. Input: JSON text saved by fetch_json() below, i.e. {"data":{"items":[show,...]}}.
Source: the GraphQL endpoint the eyefilm.nl calendar page itself uses (query `shows`, site eyeEnglish),
https://service.eyefilm.nl/graphql, no login. Show titles are placeholders ("show for: ..."), the film title
is production[0].title. Times are Europe/Amsterdam local (ISO with offset), so the first 16 chars are used as is."""
import datetime, json, subprocess, time

ENDPOINT = "https://service.eyefilm.nl/graphql"
QUERY = ("query shows($site:String!,$startDateTime:String,$offset:Int,$limit:Int,$sort:ShowSortEnum)"
         "{items:show(site:$site,startDateTime:$startDateTime,offset:$offset,limit:$limit,sort:$sort)"
         "{id url title startDateTime endDateTime cinemaRoom ticketUrl production{id url title}}}")


def fetch_json(today, out_path, ua="Mozilla/5.0"):
    """curl step: pages of 100 shows from today on (about 320 shows = 4 requests, 1 per second)."""
    items, off = [], 0
    while off <= 3000:
        body = {"query": QUERY, "variables": {"site": "eyeEnglish", "startDateTime": f"> {today} 00:00",
                                              "offset": off, "limit": 100, "sort": "DATE"}}
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", ua, "-H", "content-type: application/json",
                            "--data", json.dumps(body), ENDPOINT], capture_output=True, text=True).stdout
        d = json.loads(r)
        page = (d.get("data") or {}).get("items") or []
        if d.get("errors") and not page:
            raise RuntimeError(str(d["errors"])[:200])
        items += page
        if len(page) < 100:
            break
        off += 100
        time.sleep(1)
    json.dump({"data": {"items": items}}, open(out_path, "w"))
    return len(items)


def parse(text, today):
    try:
        items = json.loads(text)["data"]["items"] or []
    except (ValueError, KeyError, TypeError):
        return []
    end = today + datetime.timedelta(days=120)
    out, seen = [], set()
    for s in items:
        prod = s.get("production")
        prod = prod[0] if isinstance(prod, list) and prod else (prod if isinstance(prod, dict) else {})
        title = (prod.get("title") or "").strip()
        st = s.get("startDateTime") or ""
        try:
            d = datetime.date.fromisoformat(st[:10])
        except ValueError:
            continue
        if not title or not (today <= d <= end):
            continue
        h = st[11:16] if len(st) >= 16 else ""
        key = (title, d.isoformat(), h, s.get("cinemaRoom"))
        if key in seen:
            continue
        seen.add(key)
        e = {"t": title, "d": d.isoformat(), "v": "Eye Filmmuseum", "c": "film", "s": "eye",
             "u": prod.get("url") or s.get("url") or "https://www.eyefilm.nl/en/whats-on"}
        if h:
            e["h"] = h
        out.append(e)
    return out
