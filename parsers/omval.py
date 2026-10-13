"""De Omval parser (via Cineville's events API, see cineville_common.py). Input: _data/omval.json written by cineville_common.fetch_venue('omval', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "De Omval", "omval")
