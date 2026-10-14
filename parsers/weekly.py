"""Standing weekly and monthly nights that venues announce as a rule, not as dated events.

These are entered by hand from each venue's own site (source noted per rule). They are expanded into dated events for
the next 8 weeks. If a venue changes its night, edit the rule here.

Rule fields: title, venue, days (0=Monday..6=Sunday), h/eh start/end time, c category, nth (None = every week,
1..4 = that occurrence of the weekday in the month, -1 = the last one), u link, b note.
"""
from datetime import date, timedelta

HORIZON = 56

RULES = [
    # queenshead.nl/events
    {"title": "Drag Queen Bingo", "venue": "The Queen's Head", "days": [1], "h": "20:30", "c": "other",
     "u": "https://queenshead.nl/events", "nth": None},
    {"title": "Thursdays Are a Drag", "venue": "The Queen's Head", "days": [3], "h": "21:00", "c": "other",
     "u": "https://queenshead.nl/events", "nth": None},
    {"title": "Trivia Night", "venue": "The Queen's Head", "days": [2], "h": "20:30", "c": "other",
     "u": "https://queenshead.nl/events", "nth": 2},
    {"title": "Karaoke", "venue": "The Queen's Head", "days": [4], "h": "22:00", "c": "music",
     "u": "https://queenshead.nl/events", "nth": 1},
    {"title": "Showdown Monday", "venue": "The Queen's Head", "days": [0], "h": None, "c": "other",
     "u": "https://queenshead.nl/events", "nth": -1},
    # jazzcafealto.nl: live music every night, doors 20:30 (hours given by Gil from the venue)
    {"title": "Live jazz and blues", "venue": "Jazz Café Alto", "days": [0, 1, 2, 3, 6], "h": "21:30", "eh": "01:30",
     "c": "music", "u": "https://www.jazzcafealto.nl/", "nth": None, "b": "Doors 20:30. Different musicians every night, check the venue for who plays"},
    {"title": "Live jazz and blues", "venue": "Jazz Café Alto", "days": [4, 5], "h": "21:30", "eh": "02:30",
     "c": "music", "u": "https://www.jazzcafealto.nl/", "nth": None, "b": "Doors 20:30. Different musicians every night, check the venue for who plays"},
    # trutfonds.nl: party every Sunday night since 1985
    {"title": "Sunday night party", "venue": "Vereniging De Trut", "days": [6], "h": "22:00", "eh": "03:00", "c": "club",
     "u": "http://www.trutfonds.nl/", "nth": None},
    # robinfoodkollektief.nl: community dinners
    {"title": "Community dinner", "venue": "Robin Food Kollektief", "days": [0, 1, 3], "h": "18:00", "eh": "21:00",
     "c": "food", "u": "https://www.robinfoodkollektief.nl", "nth": None},
]


def _nth(d):
    """Which occurrence of its weekday in the month d is (1..5) and whether it is the last one."""
    n = (d.day - 1) // 7 + 1
    last = (d + timedelta(days=7)).month != d.month
    return n, last


def parse(text, today):
    out = []
    for r in RULES:
        d = today
        while d <= today + timedelta(days=HORIZON):
            if d.weekday() in r["days"]:
                n, last = _nth(d)
                ok = r["nth"] is None or (r["nth"] == -1 and last) or (r["nth"] == n)
                if ok:
                    e = {"t": r["title"], "d": d.isoformat(), "v": r["venue"], "c": r["c"], "u": r["u"], "s": "weekly"}
                    if r.get("h"):
                        e["h"] = r["h"]
                    if r.get("eh"):
                        e["eh"] = r["eh"]
                    if r.get("b"):
                        e["b"] = r["b"]
                    out.append(e)
            d += timedelta(days=1)
    return out
