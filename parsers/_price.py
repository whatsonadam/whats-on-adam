"""Turn the many ways venues write a price into one short, consistent string for the "p" field.

    clean("12-16€")      -> "€12-16"
    clean("0 - 15€")     -> "up to €15"
    clean("25+")         -> "from €25"
    clean("31.05")       -> "€31,05"
    clean("0")           -> "Free"
    clean("tba")         -> None   (no price known: better to show nothing than a guess)

Prices on the site are what a visitor pays, so they include VAT. Venues quote ticket prices that way.
"""
import re

NUM = re.compile(r"\d+(?:[.,]\d+)?")
UNKNOWN = re.compile(r"gulden|\btba\b|\btbc\b|\bn/?a\b|unknown|sold ?out|uitverkocht|nader te bepalen", re.I)
FREE = re.compile(r"^\s*(free|gratis|free entry|vrije toegang|free entrance)\s*$", re.I)


def _fmt(n):
    return f"{int(n)}" if n == int(n) else f"{n:.2f}".replace(".", ",")


def clean(raw):
    """Return a tidy price string, or None when there is no usable price."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or UNKNOWN.search(s):
        return None
    if FREE.match(s):
        return "Free"
    if re.search(r"[$£]", s) and "€" not in s:
        return None   # dollar or pound signs on an Amsterdam listing are almost always typos or other markets
    nums = [float(x.replace(",", ".")) for x in NUM.findall(s)]
    if not nums:
        return None
    lo, hi = min(nums), max(nums)
    if hi > 500:
        return None
    if hi == 0:
        return "Free"
    if hi < 2:
        return None   # "1" and similar are placeholders, not ticket prices
    if lo == 0:
        return f"up to €{_fmt(hi)}"
    if len(nums) == 1:
        return f"from €{_fmt(lo)}" if "+" in s else f"€{_fmt(lo)}"
    return f"€{_fmt(lo)}" if lo == hi else f"€{_fmt(lo)}-{_fmt(hi)}"


FREE_PHRASE = re.compile(r"\b(gratis toegang|toegang is gratis|entree gratis|vrije toegang|free entry|free entrance|free admission)\b", re.I)
EURO_AFTER_LABEL = re.compile(
    r"\b(?:bijdrage|entr[eé]e|tickets?|presale|kaarten|toegang|prijs|donatie|door|deur)\b\s*:?\s*(?:€|eur\b)\s*(\d+(?:[.,]\d+)?)", re.I)


def from_text(text):
    """Find a price in running text, only when it sits right after a price word ('Bijdrage: €25', 'Tickets €25,00')."""
    if not text:
        return None
    m = EURO_AFTER_LABEL.search(text)
    if m:
        return clean("€" + m.group(1))
    if FREE_PHRASE.search(text):
        return "Free"
    return None


# ---- one last tidy pass over prices that parsers already wrote (applied once, in build.py) ----
_STD = re.compile(r"^(Free|Donation|Donation, min €\d+(,\d\d)?|(from |up to )?€\d+(,\d\d)?(-\d+(,\d\d)?)?( \(door €\d+(,\d\d)?\))?)$")
_NOT_A_PRICE = re.compile(r"vegan|voku|\bopen at\b", re.I)   # Vrankrijk: price lines about the food, not the event
_DONATION_ONLY = re.compile(r"^(?:on |suggested |sliding scale )?donations?$", re.I)


def tidy(p):
    """Return (price, sold_out). Makes older parser output look like the rest: '€18.00' -> '€18',
    '€12,50 (vanaf)' -> 'from €12,50', '€10 (presale) | €12 (door)' -> '€10 (door €12)', '€8-12, 18+' -> '€8-12',
    'donation' -> 'Donation'. 'Sold out' is not a price: the site has its own badge for that, so it becomes a flag.
    Anything not recognised is left exactly as it was."""
    if not p:
        return p, False
    s = str(p).strip()
    if re.fullmatch(r"sold ?out|uitverkocht", s, re.I):
        return None, True
    if _STD.match(s):
        return s, False
    if _NOT_A_PRICE.search(s):
        return None, False
    if _DONATION_ONLY.match(s):
        return "Donation", False
    s2 = re.sub(r"\s*(?://|,)\s*18\+\s*$", "", s)          # age limit is not part of the price
    s2 = re.sub(r"\s*\((?:ticket [a-z]|vanaf)\)\s*$", lambda m: " (vanaf)" if "vanaf" in m.group(0) else "", s2, flags=re.I)
    m = re.fullmatch(r"€\s*Free", s2, re.I)
    if m:
        return "Free", False
    m = re.fullmatch(r"€\s*(\d+(?:[.,]\d+)?)(?:,-)?\s*(\(vanaf\))?", s2)
    if m:
        n = float(m.group(1).replace(",", "."))
        if n == 0:
            return "Free", False
        return (("from " if m.group(2) else "") + "€" + _fmt(n)), False
    m = re.fullmatch(r"€\s*(\d+(?:[.,]\d+)?)(?:,-)?\s*\((?:pre-?sale)\)\s*\|\s*€\s*(\d+(?:[.,]\d+)?)\s*\(door\)", s2, re.I)
    if m:
        a, b = (float(x.replace(",", ".")) for x in m.groups())
        return f"€{_fmt(a)} (door €{_fmt(b)})", False
    m = re.fullmatch(r"€\s*(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)", s2)
    if m:
        a, b = (float(x.replace(",", ".")) for x in m.groups())
        return f"€{_fmt(a)}-{_fmt(b)}", False
    return (s2 if s2 != s and _STD.match(s2) else s), False
