"""Cinema De Vlugt parser (via Cineville's events API, see cineville_common.py). Input: _data/devlugt.json written by cineville_common.fetch_venue('devlugt', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Cinema De Vlugt", "devlugt")
