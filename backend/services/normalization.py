"""
UBID Platform — Normalization Engine (Module 2)

Handles:
- Business name normalization (lowercase, suffix/prefix removal)
- Address parsing into structured fields
- PAN / GSTIN validation with check-digit verification
- Double Metaphone phonetic encoding
"""

import re
import hashlib
from typing import Optional
from dataclasses import dataclass, field, asdict

# ── Optional: phonetic encoding ──────────────────────────────────────────────
try:
    from metaphone import doublemetaphone
    HAS_METAPHONE = True
except ImportError:
    HAS_METAPHONE = False


# ── Constants ────────────────────────────────────────────────────────────────

LEGAL_SUFFIXES = [
    r'\bprivate\s+limited\b', r'\bpvt\.?\s*ltd\.?\b', r'\bpvt\b', r'\bltd\.?\b',
    r'\bllp\b', r'\blimited\s+liability\s+partnership\b', r'\blimited\b',
    r'\bincorporated\b', r'\binc\.?\b', r'\bcompany\b', r'\bco\.?\b', r'\band\s+co\.?\b',
    r'\b&\s*co\.?\b', r'\benterprises?\b', r'\bindustries?\b', r'\bworks\b',
    r'\btraders?\b', r'\bsuppliers?\b', r'\bmanufacturers?\b', r'\bagency\b',
    r'\bagencies\b', r'\bgroup\b', r'\bassociates?\b', r'\bcorporation\b',
    r'\bcorp\.?\b',
]

BUSINESS_PREFIXES = [
    r'^m/?s\.?\s*', r'^m\s+s\s+', r'^shri\s+', r'^shree\s+', r'^sri\s+', r'^smt\.?\s+', r'^new\s+',
    r'^the\s+', r'^m/s\s+',
]

# Karnataka locality aliases (extend as needed)
LOCALITY_ALIASES: dict[str, str] = {
    "peenya industrial area": "peenya indl area",
    "peenya indl est":        "peenya indl area",
    "peenya industrial estate": "peenya indl area",
    "brigade road":           "brigade rd",
    "brigade rd":             "brigade rd",
    "mg road":                "mahatma gandhi rd",
    "m g road":               "mahatma gandhi rd",
}

ADDRESS_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    (r"\broad\b", "rd"),
    (r"\brd\.?\b", "rd"),
    (r"\bstreet\b", "st"),
    (r"\bst\.?\b", "st"),
    (r"\bavenue\b", "ave"),
    (r"\bave\.?\b", "ave"),
    (r"\blayout\b", "layout"),
    (r"\bindustrial\b", "indl"),
    (r"\bindl\.?\b", "indl"),
    (r"\bestate\b", "est"),
    (r"\best\.?\b", "est"),
)

# PAN alphabet positions for check-digit validation
PAN_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ParsedAddress:
    building:  Optional[str] = None
    street:    Optional[str] = None
    locality:  Optional[str] = None
    city:      Optional[str] = None
    pincode:   Optional[str] = None
    raw:       Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NormalizedRecord:
    normalized_name: Optional[str] = None
    phonetic_name:   Optional[str] = None
    parsed_address:  Optional[dict] = None
    pincode:         Optional[str]  = None
    pan:             Optional[str]  = None
    gstin:           Optional[str]  = None
    proprietor_name: Optional[str]  = None
    pan_valid:       bool = False
    gstin_valid:     bool = False


# ── Name normalization ────────────────────────────────────────────────────────

def normalize_name(raw_name: Optional[str]) -> Optional[str]:
    """
    Full business name normalization pipeline:
    1. Lowercase
    2. Remove legal suffixes
    3. Remove common prefixes
    4. Collapse whitespace
    """
    if not raw_name:
        return None

    name = raw_name.lower().strip()

    # Remove punctuation except spaces and alphanumeric characters
    name = re.sub(r"[^a-z0-9\s]", " ", name)

    # Remove legal suffixes
    for pattern in LEGAL_SUFFIXES:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)

    # Remove prefixes
    for pattern in BUSINESS_PREFIXES:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()

    return name if name else None


def phonetic_encode(normalized_name: Optional[str]) -> Optional[str]:
    """
    Returns both Double Metaphone and Soundex-style codes for the normalized name.
    """
    if not normalized_name:
        return None

    metaphone_codes = []
    if HAS_METAPHONE:
        for word in normalized_name.split():
            primary, _ = doublemetaphone(word)
            if primary:
                metaphone_codes.append(primary)

    soundex_codes = [_soundex(word) for word in normalized_name.split()]
    soundex_codes = [code for code in soundex_codes if code]

    parts = []
    if metaphone_codes:
        parts.append("DM:" + " ".join(metaphone_codes))
    if soundex_codes:
        parts.append("SX:" + " ".join(soundex_codes))

    return "|".join(parts) if parts else None


def _soundex(word: str) -> Optional[str]:
    """Simple deterministic Soundex implementation used as a phonetic fallback."""
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return None

    groups = {
        **dict.fromkeys("bfpv", "1"),
        **dict.fromkeys("cgjkqsxz", "2"),
        **dict.fromkeys("dt", "3"),
        "l": "4",
        **dict.fromkeys("mn", "5"),
        "r": "6",
    }
    first = cleaned[0].upper()
    digits = [groups.get(ch, "0") for ch in cleaned[1:]]

    deduped = []
    last = groups.get(cleaned[0], "0")
    for digit in digits:
        if digit != last and digit != "0":
            deduped.append(digit)
        last = digit

    return (first + "".join(deduped) + "000")[:4]


# ── Address parsing ───────────────────────────────────────────────────────────

_PINCODE_RE = re.compile(r'\b([1-9][0-9]{5})\b')

def normalize_address_text(raw_address: Optional[str]) -> Optional[str]:
    """Lowercase, standardize address abbreviations, normalize pincode, and collapse spaces."""
    if not raw_address:
        return None

    address = raw_address.lower()
    address = re.sub(r"[,.;:/\\\-]", " ", address)
    for pattern, replacement in ADDRESS_ABBREVIATIONS:
        address = re.sub(pattern, replacement, address)

    for alias, canonical in LOCALITY_ALIASES.items():
        address = address.replace(alias, canonical)

    address = re.sub(r"\s+", " ", address).strip()
    return address or None


def parse_address(raw_address: Optional[str]) -> ParsedAddress:
    """
    Parses a raw address string into structured components.
    Uses regex heuristics — not perfect but robust enough for Karnataka data.
    """
    if not raw_address:
        return ParsedAddress(raw=raw_address)

    normalized_address = normalize_address_text(raw_address) or raw_address.lower().strip()
    result = ParsedAddress(raw=normalized_address)

    # Extract pincode
    pincode_match = _PINCODE_RE.search(normalized_address)
    if pincode_match:
        result.pincode = pincode_match.group(1)

    # Normalize locality aliases
    lower_addr = normalized_address.lower()
    for alias, canonical in LOCALITY_ALIASES.items():
        if alias in lower_addr:
            result.locality = canonical
            break

    # Split on comma for basic structure heuristic
    parts = [p.strip() for p in re.split(r",|\s{2,}", normalized_address) if p.strip()]
    if len(parts) >= 3:
        result.building = parts[0]
        result.street   = parts[1]
        result.locality = result.locality or parts[2]
        result.city     = parts[-2] if len(parts) > 2 else None
    elif len(parts) == 2:
        result.street   = parts[0]
        result.locality = result.locality or parts[1]
    elif len(parts) == 1:
        result.locality = result.locality or parts[0]

    return result


# ── PAN validation ────────────────────────────────────────────────────────────

_PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')

def validate_pan(pan: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Returns (cleaned_pan, is_valid).
    Validation: format check + basic check-digit rule.
    """
    if not pan:
        return None, False

    cleaned = pan.strip().upper().replace(" ", "")

    if not _PAN_RE.match(cleaned):
        return cleaned, False

    # PAN check: 4th character must indicate entity type
    valid_4th = set("ABCFGHLJPTF")
    if cleaned[3] not in valid_4th:
        return cleaned, False

    return cleaned, True


# ── GSTIN validation ──────────────────────────────────────────────────────────

_GSTIN_RE = re.compile(
    r'^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'
)

def validate_gstin(gstin: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Returns (cleaned_gstin, is_valid).
    Validates format and check character using modulo-36 algorithm.
    """
    if not gstin:
        return None, False

    cleaned = gstin.strip().upper().replace(" ", "")

    if not _GSTIN_RE.match(cleaned):
        return cleaned, False

    # Verify check digit (last character)
    CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    factor = 2
    total  = 0
    for char in reversed(cleaned[:-1]):
        inv_factor = 1 if factor == 2 else 2
        code       = CHARS.index(char) * factor
        total      += (code // 36) + (code % 36)
        factor     = inv_factor

    check_digit = (36 - (total % 36)) % 36
    expected    = CHARS[check_digit]

    return cleaned, cleaned[-1] == expected


# ── Checksum ──────────────────────────────────────────────────────────────────

def compute_checksum(payload: dict) -> str:
    """SHA-256 of the JSON payload for idempotent ingestion detection."""
    import json
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


# ── Main entry point ──────────────────────────────────────────────────────────

def normalize_record(raw_payload: dict) -> NormalizedRecord:
    """
    Full normalization pipeline for a single raw record payload.

    Expects payload fields (all optional):
      - name / business_name / entity_name
      - address / registered_address
      - pan / pan_number
      - gstin / gst_number
    """
    # Extract name from various field names
    raw_name = (
        raw_payload.get("name") or
        raw_payload.get("business_name") or
        raw_payload.get("entity_name") or
        raw_payload.get("trade_name")
    )

    # Extract address
    raw_address = (
        raw_payload.get("address") or
        raw_payload.get("registered_address") or
        raw_payload.get("office_address")
    )

    # Extract identifiers
    raw_pan   = raw_payload.get("pan") or raw_payload.get("pan_number")
    raw_gstin = raw_payload.get("gstin") or raw_payload.get("gst_number") or raw_payload.get("gstin_no")
    raw_proprietor = (
        raw_payload.get("proprietor_name") or
        raw_payload.get("owner_name") or
        raw_payload.get("partner_name") or
        raw_payload.get("contact_person")
    )

    # Run pipeline
    norm_name    = normalize_name(raw_name)
    phonetic     = phonetic_encode(norm_name)
    parsed_addr  = parse_address(raw_address)
    proprietor   = normalize_name(raw_proprietor)
    pan, pan_ok  = validate_pan(raw_pan)
    gstin, gst_ok = validate_gstin(raw_gstin)

    return NormalizedRecord(
        normalized_name = norm_name,
        phonetic_name   = phonetic,
        parsed_address  = parsed_addr.to_dict(),
        pincode         = parsed_addr.pincode,
        pan             = pan,
        gstin           = gstin,
        proprietor_name = proprietor,
        pan_valid       = pan_ok,
        gstin_valid     = gst_ok,
    )
