"""Het Documentaire Paviljoen parser (via Cineville's events API, see cineville_common.py). Input: _data/docpaviljoen.json written by cineville_common.fetch_venue('docpaviljoen', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Het Documentaire Paviljoen", "docpaviljoen")
