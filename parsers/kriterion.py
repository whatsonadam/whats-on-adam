"""Kriterion via Cineville's events API (kriterion.nl itself blocks automated readers). See cineville_common.py."""
import cineville_common as cv

def parse(text, today):
    return cv.parse_venue(text, today, "Kriterion", "kriterion")
