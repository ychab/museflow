import re
import unicodedata

from unidecode import unidecode

from museflow.domain.types import LocaleCode


def validate_locale(value: object) -> LocaleCode | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if len(value) == 2 and value.isalpha() else None


def validate_locales(value: object) -> list[LocaleCode] | None:
    """Keep the valid codes of a list, deduplicated in order.

    An empty list is a valid answer (no sung language). A non-list, or a non-empty list without any valid code, is not
    an answer and returns None.
    """
    if not isinstance(value, list):
        return None
    codes = list(dict.fromkeys(code for item in value if (code := validate_locale(item)) is not None))
    return codes if codes or not value else None


def unidecode_lower_text(text: str) -> str:
    """Remove accents and convert to lowercase"""
    return unidecode(text).lower()


def slugify(text: str, max_length: int) -> str:
    """Lowercase ASCII words joined by hyphens ("Soirées d'hiver" → "soirees-d-hiver"); empty without a letter or digit."""
    slug = re.sub(r"[^a-z0-9]+", "-", unidecode_lower_text(text)).strip("-")
    return slug[:max_length].rstrip("-")


def normalize_text(text: str) -> str:
    text = unidecode_lower_text(text)

    # Remove "feat", "feat.", "ft", "ft.", "remaster", "radio edit" in brackets or parentheses
    text = re.sub(r"[\(\[].*?(feat\.?|ft\.?|remaster|live|edit|version).*?[\)\]]", "", text)

    # Remove trailing suffixes after hyphens
    text = re.sub(r"\s*-\s*.*?(feat\.?|ft\.?|remaster|live|edit|version|mono|stereo).*", "", text)

    # Remove purely non-alphanumeric noise and extra whitespace
    text = re.sub(r"[^\w\s]", "", text)

    return " ".join(text.split())


def strip_control_chars(text: str) -> str:
    """Removes the control characters (NUL, ESC, ...) an LLM may emit in place of a letter, then collapses whitespace."""
    text = "".join(" " if unicodedata.category(char) == "Cc" else char for char in text)
    return " ".join(text.split())


def generate_fingerprint(name: str, artist_names: list[str]) -> str:
    clean_track = normalize_text(name)
    clean_artist = normalize_text(artist_names[0]) if artist_names else "unknown"

    return f"{clean_track}|{clean_artist}"


def get_fingerprint_title(fingerprint: str) -> str:
    """Returns the normalized title of a fingerprint: its part before `|`, which the title never holds."""
    return fingerprint.partition("|")[0]
