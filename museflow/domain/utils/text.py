import re

from unidecode import unidecode

from museflow.domain.types import LocaleCode


def validate_locale(v: object) -> LocaleCode | None:
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if len(v) == 2 and v.isalpha() else None


def validate_locales(v: object) -> list[LocaleCode] | None:
    """Keep the valid codes of a list, deduplicated in order.

    An empty list is a valid answer (no sung language). A non-list, or a non-empty list without any valid code, is not
    an answer and returns None.
    """
    if not isinstance(v, list):
        return None
    codes = list(dict.fromkeys(code for item in v if (code := validate_locale(item)) is not None))
    return codes if codes or not v else None


def unidecode_lower_text(text: str) -> str:
    """Remove accents and convert to lowercase"""
    return unidecode(text).lower()


def normalize_text(text: str) -> str:
    text = unidecode_lower_text(text)

    # Remove "feat", "feat.", "ft", "ft.", "remaster", "radio edit" in brackets or parentheses
    text = re.sub(r"[\(\[].*?(feat\.?|ft\.?|remaster|live|edit|version).*?[\)\]]", "", text)

    # Remove trailing suffixes after hyphens
    text = re.sub(r"\s*-\s*.*?(feat\.?|ft\.?|remaster|live|edit|version|mono|stereo).*", "", text)

    # Remove purely non-alphanumeric noise and extra whitespace
    text = re.sub(r"[^\w\s]", "", text)

    return " ".join(text.split())


def generate_fingerprint(name: str, artist_names: list[str]) -> str:
    clean_track = normalize_text(name)
    clean_artist = normalize_text(artist_names[0]) if artist_names else "unknown"

    return f"{clean_track}|{clean_artist}"
