"""Cinema Amstelveen parser (via Cineville's events API, see cineville_common.py). Input: _data/amstelveen.json written by cineville_common.fetch_venue('amstelveen', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Cinema Amstelveen", "amstelveen")
