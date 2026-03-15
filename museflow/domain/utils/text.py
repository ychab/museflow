import re

from unidecode import unidecode


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
