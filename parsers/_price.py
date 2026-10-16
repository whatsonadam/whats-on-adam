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
