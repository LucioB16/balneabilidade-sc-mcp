"""Text, date and numeric normalization for IMA/SC data.

Portuguese labels are preserved by callers; this module only folds
names for matching and parses the documented value formats.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, time

from .models import Classification

PORTUGUESE_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


def fold(text: str) -> str:
    """Accent- and case-insensitive matching key.

    Praia de Perequê and PRAIA DE PEREQUE produce the same key. The original
    string is never replaced in output models.
    """

    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_marks.casefold().split())


def slugify(text: str) -> str:
    """Stable ASCII key for internal beach keys, not an IMA code."""

    folded = fold(text)
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return slug or "unnamed"


def point_key(municipality: str, beach: str, point: str) -> str:
    """Canonical join key for a sampling point."""

    return f"{fold(municipality)}|{fold(beach)}|{fold(point)}"


def beach_key(municipality: str, beach: str) -> str:
    return f"{slugify(municipality)}|{slugify(beach)}"


def parse_br_date(value: str) -> date:
    """Parse the IMA date format dd/MM/yyyy."""

    return date(int(value[6:10]), int(value[3:5]), int(value[0:2]))


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_time(value: str) -> time | None:
    value = value.strip()
    if not value:
        return None
    hour, minute = value.split(":", 1)
    return time(int(hour), int(minute))


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_ecoli(value: str | None) -> tuple[int | None, str, str]:
    """Return (numeric_value, qualifier, raw).

    <20 remains a censored below-20 result, never exactly 20. > 24196 and
    >24196 are both accepted.
    """

    raw = (value or "").strip()
    if not raw:
        return None, "unknown", raw
    match = re.fullmatch(r"([<>])?\s*(\d+)", raw)
    if not match:
        return None, "unknown", raw
    qualifier = "below" if match.group(1) == "<" else "above" if match.group(1) == ">" else "exact"
    return int(match.group(2)), qualifier, raw


def classification_from_label(value: str | None) -> Classification:
    """Map Portuguese labels without translating or re-deriving the verdict."""

    folded = fold(value or "")
    if folded.startswith("impr"):
        return Classification.IMPROPER
    if folded.startswith("pr"):
        return Classification.PROPER
    if folded.startswith("ind"):
        return Classification.INDETERMINATE
    return Classification.UNKNOWN


def is_in_season(day: date) -> bool:
    """IMA samples weekly from October to March and monthly from April to September."""

    return day.month >= 10 or day.month <= 3


def point_number(point_name: str) -> int | None:
    """Extract the Ponto NN number without treating it as an ID."""

    match = re.search(r"Ponto\s+(\d+)", point_name, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_collection_dates(text: str) -> tuple[date, ...]:
    """Extract the dates IMA says were collected for a bulletin.

    Handles both the current weekly prose (dias 09, 10 e 11 de novembro de
    2026) and the off-season single-day prose (no dia 21 de setembro de
    2026). Returns an empty tuple when the prose is not understood.
    """

    found: list[date] = []
    pattern = re.compile(
        r"(?:dias?|no dia)\s+((?:\d{1,2})(?:\s*,\s*\d{1,2})*(?:\s+e\s+\d{1,2})?)\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        days = [int(part) for part in re.findall(r"\d{1,2}", match.group(1))]
        month = PORTUGUESE_MONTHS.get(fold(match.group(2)))
        year = int(match.group(3))
        if month is None:
            continue
        for day in days:
            try:
                found.append(date(year, month, day))
            except ValueError:
                continue
    return tuple(dict.fromkeys(found))
