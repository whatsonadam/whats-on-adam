"""Bijlmerbios parser (via Cineville's events API, see cineville_common.py). Input: _data/bijlmerbios.json written by cineville_common.fetch_venue('bijlmerbios', today, path)."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Bijlmerbios", "bijlmerbios")
