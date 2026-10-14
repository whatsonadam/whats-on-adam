"""Resident Advisor: Amsterdam listings from RA's public event listing API (JSON, one file per page of 100).

fetch() is called by fetch.py and writes _data/ra/pNNN.json; parse_pages() is called by build.py.
RA times are local Amsterdam time already. Nights that run past midnight keep the start date.
"""
import datetime, json, os, re, subprocess, tempfile, time

URL = "https://ra.co/graphql"
AREA_AMSTERDAM = 29
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
QUERY = ("query GET_EVENT_LISTINGS($filters: FilterInputDtoInput, $filterOptions: FilterOptionsInputDtoInput, "
         "$page: Int, $pageSize: Int, $sort: SortInputDtoInput) { eventListings(filters: $filters, "
         "filterOptions: $filterOptions, pageSize: $pageSize, page: $page, sort: $sort) { data { id listingDate "
         "event { id title date startTime endTime contentUrl isTicketed venue { id name area { name } } "
         "artists { name } genres { name } } } totalResults } }")
LIVE = re.compile(r"\b(live|concert|orchestra|choir|recital)\b", re.I)


def _post(payload, out):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f); body = f.name
    try:
        r = subprocess.run(["curl", "-sS", "-m", "60", "-X", "POST", URL, "-H", "Content-Type: application/json",
                            "-H", "Referer: https://ra.co/events/nl/amsterdam", "-A", UA, "--data", "@" + body,
                            "-o", out, "-w", "%{http_code}"], capture_output=True, text=True)
        return r.stdout.strip()
    finally:
        os.remove(body)


def fetch(out_dir, today, days=60, page_size=100, max_pages=30):
    """Download the next `days` days of Amsterdam listings, one page per second. Returns the number of listings."""
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir): os.remove(os.path.join(out_dir, f))
    to = today + datetime.timedelta(days=days)
    n = 0
    for p in range(1, max_pages + 1):
        payload = {"operationName": "GET_EVENT_LISTINGS", "query": QUERY, "variables": {
            "filters": {"areas": {"eq": AREA_AMSTERDAM},
                        "listingDate": {"gte": today.isoformat() + "T00:00:00.000Z", "lte": to.isoformat() + "T00:00:00.000Z"}},
            "filterOptions": {"genre": True}, "pageSize": page_size, "page": p,
            "sort": {"listingDate": {"order": "ASCENDING"}, "score": {"order": "DESCENDING"},
                     "titleKeyword": {"order": "ASCENDING"}}}}
        out = os.path.join(out_dir, f"p{p:03d}.json")
        code = _post(payload, out)
        if code != "200": raise RuntimeError(f"RA returned {code} on page {p}")
        try: items = json.load(open(out))["data"]["eventListings"]["data"]
        except Exception: raise RuntimeError(f"RA page {p} was not valid data")
        if not items: os.remove(out); break
        n += len(items)
        if len(items) < page_size: break
        time.sleep(1.0)
    return n


def parse_pages(pages, today):
    out, seen = [], set()
    for page in pages:
        try: items = page["data"]["eventListings"]["data"]
        except Exception: continue
        for it in items:
            v = it.get("event") or {}
            if not v.get("title") or v.get("id") in seen: continue
            seen.add(v["id"])
            try:
                start = datetime.datetime.fromisoformat((v.get("startTime") or v["date"])[:19])
            except Exception:
                continue
            if start.date() < today: continue
            title = re.sub(r"\s+", " ", v["title"]).strip()
            ev = {"t": title, "d": start.date().isoformat(), "v": (v.get("venue") or {}).get("name") or "",
                  "u": "https://ra.co" + (v.get("contentUrl") or ""), "c": "music" if LIVE.search(title) else "club", "s": "ra"}
            if v.get("startTime") and start.strftime("%H:%M") != "00:00": ev["h"] = start.strftime("%H:%M")
            artists = [a["name"] for a in v.get("artists") or [] if a.get("name")]
            if artists: ev["b"] = ", ".join(artists[:4])[:120]
            out.append(ev)
    return out
