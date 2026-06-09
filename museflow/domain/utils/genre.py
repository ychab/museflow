from unidecode import unidecode


def normalize_genre_key(genre: str) -> str:
    genre = unidecode(genre).lower()
    genre = genre.replace("-", " ")
    genre = " ".join(genre.split())

    if genre.endswith("s") and len(genre) - 1 >= 6:
        genre = genre[:-1]

    return genre


def deduplicate_genre_dict(genres: dict[str, float]) -> dict[str, float]:
    """Merge duplicate genre keys after normalization, summing weights capped at 1.0.

    Slash-compound genres (e.g. "hip hop/rap") are expanded into their atomic parts,
    each receiving the full weight, before deduplication.
    """
    merged: dict[str, float] = {}
    for key, weight in genres.items():
        parts = [p.strip() for p in key.split("/")] if "/" in key else [key]
        for part in parts:
            normalized = normalize_genre_key(part)
            merged[normalized] = min(1.0, merged.get(normalized, 0.0) + weight)
    return merged
