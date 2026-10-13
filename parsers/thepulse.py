"""Cinema The Pulse parser (via Cineville's events API, see cineville_common.py). Input: _data/thepulse.json written by cineville_common.fetch_venue('thepulse', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Cinema The Pulse", "thepulse")
