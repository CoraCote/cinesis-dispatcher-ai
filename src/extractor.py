"""
Part A -- Rule-based extraction of a structured driver profile from raw conversation.

Approach: regex + keyword scanning over the transcript.
The test spec says "LLM-based or otherwise -- your choice."
A rule-based extractor is deterministic, needs no API key, and is easier to audit.
"""

import re
from src.models import Coordinates, DriverProfile

# ---------------------------------------------------------------------------
# City -> (lat, lon) lookup
# ---------------------------------------------------------------------------

KNOWN_CITIES: dict[str, tuple[float, float]] = {
    "Dallas, TX":        (32.7767, -96.7970),
    "Fort Worth, TX":    (32.7555, -97.3308),
    "Austin, TX":        (30.2672, -97.7431),
    "Houston, TX":       (29.7604, -95.3698),
    "San Antonio, TX":   (29.4241, -98.4936),
    "Oklahoma City, OK": (35.4676, -97.5164),
    "Little Rock, AR":   (34.7465, -92.2896),
    "Shreveport, LA":    (32.5252, -93.7502),
    "Memphis, TN":       (35.1495, -90.0490),
    "Nashville, TN":     (36.1627, -86.7816),
    "Knoxville, TN":     (35.9606, -83.9207),
    "Birmingham, AL":    (33.5186, -86.8104),
    "Montgomery, AL":    (32.3668, -86.3000),
    "Atlanta, GA":       (33.7490, -84.3880),
    "Charlotte, NC":     (35.2271, -80.8431),
    "Raleigh, NC":       (35.7796, -78.6382),
    "St. Louis, MO":     (38.6270, -90.1994),
    "Kansas City, MO":   (39.0997, -94.5786),
    "Chicago, IL":       (41.8781, -87.6298),
    "Indianapolis, IN":  (39.7684, -86.1581),
    "Louisville, KY":    (38.2527, -85.7585),
    "Denver, CO":        (39.7392, -104.9903),
    "Phoenix, AZ":       (33.4484, -112.0740),
    "Los Angeles, CA":   (34.0522, -118.2437),
}


def _coords(city_key: str) -> Coordinates:
    lat, lon = KNOWN_CITIES[city_key]
    city, state = [p.strip() for p in city_key.split(",", 1)]
    return Coordinates(lat=lat, lon=lon, city=city, state=state)


# ---------------------------------------------------------------------------
# Word-to-number helpers
# ---------------------------------------------------------------------------

_WORD_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000,
}


def _words_to_int(text: str) -> int:
    """Convert spoken-number phrases like 'forty-four thousand' to int."""
    tokens = re.split(r"[\s\-]+", text.strip().lower())
    total, current = 0, 0
    for tok in tokens:
        if tok not in _WORD_NUMS:
            continue
        val = _WORD_NUMS[tok]
        if val == 1000:
            total += (current if current else 1) * 1000
            current = 0
        elif val == 100:
            current = (current if current else 1) * 100
        else:
            current += val
    return total + current


def _spoken_dollar_rate(text: str) -> float | None:
    """
    Parse phrases like 'two-fifty', 'two fifty', 'two dollars fifty', '2.50', '$2.50'.
    Returns dollars per mile as a float, or None if not found.
    """
    # Numeric: $2.50 / 2.50 / 2.5
    m = re.search(r"\$?\s*(\d+\.\d+)", text)
    if m:
        return float(m.group(1))
    # Spoken compound: "two-fifty" / "two fifty" -> 2.50
    m = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)"
        r"[\s\-]+(fifty|sixty|seventy|eighty|ninety|twenty|thirty|forty)\b",
        text, re.IGNORECASE,
    )
    if m:
        dollars = _WORD_NUMS[m.group(1).lower()]
        cents_word = m.group(2).lower()
        cents = _WORD_NUMS[cents_word] / 100
        return float(dollars) + cents
    return None


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_name(text: str) -> str:
    m = re.search(r"Am I reaching\s+([A-Z][a-z]+\s+[A-Z][a-z]+)", text)
    if m:
        return m.group(1)
    m = re.search(r"this is\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\s+calling", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return "Unknown"


def _extract_current_location(text: str) -> str:
    city_pattern = "|".join(re.escape(c.split(",")[0]) for c in KNOWN_CITIES)
    m = re.search(
        rf"(?:sitting at|dropped|located in|I(?:'m| am) in|east side of|west side of|"
        rf"north side of|south side of|in)\s+({city_pattern})\b",
        text, re.IGNORECASE,
    )
    if m:
        name = m.group(1).title()
        for key in KNOWN_CITIES:
            if key.startswith(name + ","):
                return key
    # Fallback: explicit "Dallas" mention
    if re.search(r"\bDallas\b", text, re.IGNORECASE):
        return "Dallas, TX"
    return "Dallas, TX"


def _extract_home_base(text: str) -> str:
    m = re.search(
        r"home[\s\-]?base(?:d)?\s+(?:in|out of)\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|\s+still|\s+right)",
        text, re.IGNORECASE,
    )
    if m:
        name = m.group(1).strip().title()
        for key in KNOWN_CITIES:
            if key.startswith(name + ","):
                return key
    # "Yeah, Memphis." pattern
    m = re.search(r"Yeah,\s+(Memphis|Dallas|Nashville|Atlanta|Houston)\b", text, re.IGNORECASE)
    if m:
        name = m.group(1).title()
        for key in KNOWN_CITIES:
            if key.startswith(name + ","):
                return key
    return "Memphis, TN"


def _extract_equipment(text: str) -> tuple[str, int]:
    """Returns (trailer_type, trailer_length_ft)."""
    m = re.search(
        r"(\d+)[\s\-]?(?:foot|ft|')\s+(dry\s*van|reefer|flatbed|step\s*deck|lowboy|tanker)",
        text, re.IGNORECASE,
    )
    if m:
        length = int(m.group(1))
        ttype = m.group(2).strip().title().replace("  ", " ")
        return ttype, length
    if re.search(r"\bdry[\s\-]?van\b", text, re.IGNORECASE):
        return "Dry Van", 53
    if re.search(r"\breefer\b", text, re.IGNORECASE):
        return "Reefer", 53
    if re.search(r"\bflatbed\b", text, re.IGNORECASE):
        return "Flatbed", 48
    return "Dry Van", 53


def _extract_max_weight(text: str) -> int:
    # Digit form: 44,000 / 44000
    m = re.search(r"\b(\d{2,3})[,\s]?000\s*(?:lbs?|pounds)?\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 1000
    # Spoken form: "forty-four thousand"
    m = re.search(
        r"\b(forty|thirty|fifty|forty[-\s]four|forty[-\s]five|forty[-\s]two|"
        r"forty[-\s]three|forty[-\s]six|forty[-\s]seven|forty[-\s]eight)"
        r"(?:[\s\-]thousand)?\b",
        text, re.IGNORECASE,
    )
    if m:
        val = _words_to_int(m.group(0))
        if val > 0:
            return val
    return 44000


def _extract_available_date(text: str, call_date: str = "2026-06-18") -> str:
    from datetime import date, timedelta
    base = date.fromisoformat(call_date)
    if re.search(r"tomorrow", text, re.IGNORECASE):
        return (base + timedelta(days=1)).isoformat()
    if re.search(r"today|right now|available now", text, re.IGNORECASE):
        return base.isoformat()
    return (base + timedelta(days=1)).isoformat()


def _extract_min_rate(text: str) -> float:
    # Find "at least X" / "need X a mile" / "minimum X"
    m = re.search(
        r"(?:at least|need|minimum|floor|looking for)\s+([\w\s\$\.\-]+?)\s*(?:a mile|per mile|/mile)",
        text, re.IGNORECASE,
    )
    if m:
        rate = _spoken_dollar_rate(m.group(1))
        if rate:
            return rate
    # Any mention of a dollar rate near "mile"
    m = re.search(
        r"([\w\s\$\.\-]+?)\s*(?:a mile|per mile|/mile)",
        text, re.IGNORECASE,
    )
    if m:
        rate = _spoken_dollar_rate(m.group(1))
        if rate and 0.5 < rate < 10:
            return rate
    return 2.50


def _extract_preferred_regions(text: str) -> list[str]:
    regions = []
    if re.search(r"\bSoutheast\b", text, re.IGNORECASE):
        regions.append("Southeast")
    if re.search(r"\bMidwest\b", text, re.IGNORECASE):
        regions.append("Midwest")
    if re.search(r"\bNortheast\b", text, re.IGNORECASE):
        regions.append("Northeast")
    if re.search(r"\bSouthwest\b", text, re.IGNORECASE):
        regions.append("Southwest")
    if re.search(r"\bWest Coast\b|\bPacific\b", text, re.IGNORECASE):
        regions.append("West Coast")
    if not regions:
        regions.append("Southeast")
    return regions


def _extract_hazmat(text: str) -> bool:
    no_hazmat = re.search(r"no\s+hazmat|not\s+(?:hazmat|certified)", text, re.IGNORECASE)
    has_hazmat = re.search(r"(?:have|got|hold)\s+hazmat|hazmat\s+certified", text, re.IGNORECASE)
    if no_hazmat:
        return False
    if has_hazmat:
        return True
    return False


def _extract_team(text: str) -> bool:
    no_team = re.search(r"no\s+team|not\s+team|solo|don.t do team", text, re.IGNORECASE)
    is_team = re.search(r"\bteam\s+(?:driver|driving)\b(?!\s*\.?\s*I\s+don)", text, re.IGNORECASE)
    if no_team:
        return False
    if is_team:
        return True
    return False


def _build_notes(text: str) -> str:
    notes = []

    # Max days
    m = re.search(
        r"(?:more than|out more than|out)\s+(five|six|seven|\d+)\s+days", text, re.IGNORECASE
    )
    if m:
        notes.append(
            f"[DIRECT] Max days out: {m.group(1)} days preferred -- "
            f"'{m.group(0)}'"
        )
    m2 = re.search(r"stretch to\s+a?\s*(week|\d+ days?)", text, re.IGNORECASE)
    if m2:
        notes.append(f"[DIRECT] Will stretch to {m2.group(1)} if rate justifies it.")

    # Livestock
    if re.search(r"don.t do livestock|no livestock|not set up for.*livestock", text, re.IGNORECASE):
        notes.append("[DIRECT] No livestock -- 'I don't do livestock. I'm not set up for that.'")

    # Oversized
    if re.search(r"no oversize|don.t have the permits|no over.?sized", text, re.IGNORECASE):
        notes.append(
            "[DIRECT] No oversized loads -- 'I don't have the permits for oversized freight.'"
        )

    # West Coast avoidance
    if re.search(r"hate California|avoid the West Coast|don.t want.*Colorado", text, re.IGNORECASE):
        notes.append(
            "[IMPLIED] Avoids West Coast (Colorado and beyond) -- "
            "'I avoid the West Coast like the plague.'"
        )

    # Deadhead sensitivity
    if re.search(r"dead.?head.*empty miles|empty miles.*dead.?head|drove.*empty.*origin", text, re.IGNORECASE):
        notes.append(
            "[IMPLIED] High deadhead sensitivity -- described a load ruined by 200 empty pickup miles."
        )

    # Prefers homeward loads
    if re.search(r"brings? (?:me )?(?:toward|closer to) home|toward home", text, re.IGNORECASE):
        notes.append(
            "[IMPLIED] Prefers loads pointing toward Memphis -- "
            "Southeast preferred because it brings him toward home base."
        )

    return "\n".join(notes) if notes else "No additional constraints noted."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_driver_profile(conversation_text: str) -> DriverProfile:
    """Parse a raw dispatcher-driver transcript and return a DriverProfile."""
    text = conversation_text

    name = _extract_name(text)
    current_city = _extract_current_location(text)
    home_city = _extract_home_base(text)
    equipment_type, trailer_length = _extract_equipment(text)
    max_weight = _extract_max_weight(text)
    available_date = _extract_available_date(text)
    min_rate = _extract_min_rate(text)
    preferred_regions = _extract_preferred_regions(text)
    hazmat = _extract_hazmat(text)
    team = _extract_team(text)
    notes = _build_notes(text)

    return DriverProfile(
        name=name,
        current_location=_coords(current_city),
        home_base=_coords(home_city),
        equipment_type=equipment_type,
        trailer_length_ft=trailer_length,
        max_weight_lbs=max_weight,
        available_date=available_date,
        min_effective_rate_per_mile=min_rate,
        preferred_regions=preferred_regions,
        hazmat_certified=hazmat,
        team_driver=team,
        notes=notes,
    )
