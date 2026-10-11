"""Parser for De Sering (desering.org/events)."""
import re
import datetime

BASE_URL = "https://desering.org"

ENTRY_RE = re.compile(
    r'\[(\d{2})\.(\d{2})\.\s*\n\n(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})\s*\n\n'
    r'(.*?)\]\((/event/[^)]+)\)',
    re.DOTALL,
)

CATEGORY_KEYWORDS = [
    (("workshop",), "workshop"),
    (("hard techno", "hardcore", "hard bounce", "neo rave", "rave", "party",
      "ade", "nighttime event", "techno", "toilet radio"), "club"),
    (("taal cafe", "climate drinks", "book club", "learn dutch"), "community"),
    (("film", "screening", "animation", "flimmaking"), "film"),
]


def _classify(title: str, tag_lines: list[str]) -> str:
    haystack = " ".join([title] + tag_lines).lower()
    for keywords, cat in CATEGORY_KEYWORDS:
        if any(k in haystack for k in keywords):
            return cat
    return "other"


def parse(text: str, today: datetime.date) -> list[dict]:
    window_end = today + datetime.timedelta(days=120)
    events = []

    for m in ENTRY_RE.finditer(text):
        dd, mm, h1, m1, h2, m2, body, path = m.groups()
        try:
            day = int(dd)
            month = int(mm)
        except ValueError:
            continue

        # Year inference: month more than ~2 months before today's month -> next year.
        year = today.year
        if month < today.month - 2:
            year += 1
        try:
            date = datetime.date(year, month, day)
        except ValueError:
            continue

        if not (today <= date <= window_end):
            continue

        lines = [l.strip() for l in body.split("\n") if l.strip()]
        if not lines:
            continue
        title = lines[0]
        tag_lines = lines[1:]

        events.append({
            "t": title,
            "d": date.isoformat(),
            "h": f"{h1}:{m1}",
            "eh": f"{h2}:{m2}",
            "v": "De Sering",
            "u": BASE_URL + path,
            "c": _classify(title, tag_lines),
            "s": "desering",
        })

    return events
