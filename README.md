# What's on A'dam

A free, non-commercial agenda that puts events from Amsterdam venues and agendas in one place.
Every event links back to its original listing. No ads, no tickets, no tracking.

## How it works

Twice a day GitHub runs `.github/workflows/refresh.yml`:

1. `fetch.py` downloads each source page into `_data/` (headless Chromium, the radar.squat.net API and I amsterdam's listing pages).
2. `build.py` runs one small parser per source (`parsers/<source>.py`), removes duplicates across sources, flags Dutch-language events, adds locations and districts (`geo.py`), and writes `public/index.html` + `public/events.json`.
3. The `public/` folder is published with GitHub Pages.

If a source fails or is blocked on a run, the site keeps that source's events from the previous run.

## Maintaining it

- **A source stopped working** (the build log says "nothing parsed" or "kept previous data"): the venue changed its website. Adjust `parsers/<source>.py`.
- **Add a source:** add its URL to `PAGES` in `fetch.py`, write `parsers/<key>.py` with `parse(text, today) -> list[event]`, and add it to `MD_KEYS` and `SOURCES` in `build.py`.
- **A venue is in the wrong place on the map:** edit its entry in `venues.json` (lat, lon, area). Entries are never overwritten. Unknown venues are looked up automatically with Photon (OpenStreetMap data).
- **Contact address on the site:** set a repository variable `CONTACT_EMAIL` (Settings → Secrets and variables → Actions → Variables).
- **Manual refresh:** Actions → Refresh agenda → Run workflow.

Event field names in `events.json`: t title, d date, ed end date, h/eh start/end time, v venue, u link, c category,
p price, b short description, s source, nl looks Dutch-language, la/lo coordinates, ar district, a also listed on.

Map © OpenStreetMap contributors. District borders: Gemeente Amsterdam open data.
