# What's on A'dam

A free, non-commercial agenda that puts events from Amsterdam venues and agendas in one place.
Every event links back to its original listing. No ads, no tickets, no tracking.

## How it works

Twice a day GitHub runs `.github/workflows/refresh.yml`:

1. `fetch.py` downloads each source page into `_data/` (headless Chromium, the radar.squat.net API and I amsterdam's listing pages).
2. `build.py` runs one small parser per source (`parsers/<source>.py`), removes duplicates across sources, flags Dutch-language events, adds locations and districts (`geo.py`), and writes `public/index.html` + `public/events.json`.
3. The `public/` folder is published with GitHub Pages.

If a source fails or is blocked on a run, the site keeps that source's events from the previous run.

Some agenda pages list no start time. `pagetimes.py` opens those events' own pages once (Tolhuistuin, Cinetol,
I amsterdam), reads the time and remembers it in `times.json`, so later runs only visit new events. At most 300
pages per run, one per second. Events whose page has no time stay as "Time to be confirmed".

## Maintaining it

- **A source stopped working** (the build log says "nothing parsed" or "kept previous data"): the venue changed its website. Adjust `parsers/<source>.py`.
- **Add a source:** add its URL to `PAGES` in `fetch.py`, write `parsers/<key>.py` with `parse(text, today) -> list[event]`, and add it to `MD_KEYS` and `SOURCES` in `build.py`.
- **A venue is in the wrong place on the map:** edit its entry in `venues.json` (lat, lon, area). Entries are never overwritten. Unknown venues are looked up automatically with Photon (OpenStreetMap data).
- **Contact address on the site:** set a repository variable `CONTACT_EMAIL` (Settings → Secrets and variables → Actions → Variables).
- **Manual refresh:** Actions → Refresh agenda → Run workflow.

## Protest and activism sources

Four national agendas are read for Amsterdam entries only: Wat kan ik doen? (its public JSON API), The Rights Forum,
Extinction Rebellion NL and socialisme.nu. All of them show under the Protest category and are never hidden by the
English-friendly filter. When the same protest comes from several agendas, `merge_protests` in `build.py` keeps one
(same day, two shared title words, start times within an hour).

Their Dutch text is translated by `translate.py` with the DeepL API. Add the key as a repository secret named
`DEEPL_API_KEY` (Settings → Secrets and variables → Actions → Secrets). Translations are saved in `translations.json`
so each text is translated once. Without a key the original text stays. The Dutch title is kept in field `to`.
Watkanikdoen has a small `PLACE_OVERRIDES` list in `parsers/watkanikdoen.py` for actions whose place is announced
elsewhere but not filled in on the site yet.

Event field names in `events.json`: t title, d date, ed end date, h/eh start/end time, v venue, u link, c category,
p price, b short description, s source, nl looks Dutch-language, to original title when translated, la/lo coordinates,
ar district, a also listed on.

## Agenda filters

With only the Protest type ticked, the day strip is replaced by one list of the next 4 weeks grouped by date (button
"Pick a day" brings the strip back). Double click, double tap or long press on a type chip shows only that type; doing it
again on the only one brings all types back.

Map © OpenStreetMap contributors. District borders: Gemeente Amsterdam open data.
