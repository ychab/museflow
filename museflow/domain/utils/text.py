import re
import unicodedata

from unidecode import unidecode

from museflow.domain.types import LocaleCode

# Applied to both sides of a comparison, in English and French, the languages most titles are in.
_NUMBER_WORDS = {
    word: str(number)
    for words in (
        ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
        ("zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"),
    )
    for number, word in enumerate(words)
} | {"une": "1"}


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


def strip_brackets(text: str) -> str:
    """Removes the bracketed parts of a title, e.g. "Night Ride (Interlude)"; keeps the text if nothing else is left."""
    stripped = " ".join(re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", text).split())
    return stripped or text


def normalize_numbers(text: str) -> str:
    """Writes the small numbers of a normalized text as digits, so that "one night" and "1 night" compare equal."""
    return " ".join(_NUMBER_WORDS.get(word, word) for word in text.split())


def strip_control_chars(text: str) -> str:
    """Removes the control characters (NUL, ESC, ...) an LLM may emit in place of a letter, then collapses whitespace."""
    text = "".join(" " if unicodedata.category(char) == "Cc" else char for char in text)
    return " ".join(text.split())


def generate_fingerprint(name: str, artist_names: list[str]) -> str:
    clean_track = normalize_text(name)
    clean_artist = normalize_text(artist_names[0]) if artist_names else "unknown"

    return f"{clean_track}|{clean_artist}"
