import pytest

from museflow.domain.utils.genre import deduplicate_genre_dict
from museflow.domain.utils.genre import normalize_genre_key


class TestNormalizeGenreKey:
    @pytest.mark.parametrize(
        ("genre", "expected"),
        [
            pytest.param("hip-hop", "hip hop", id="hyphen_to_space"),
            pytest.param("Hip-Hop", "hip hop", id="uppercase_and_hyphen"),
            pytest.param("french hip-hop", "french hip hop", id="compound_with_hyphen"),
            pytest.param("afrobeats", "afrobeat", id="trailing_s_stripped"),
            pytest.param("blues", "blues", id="trailing_s_kept_short_result"),
            pytest.param("hip hop", "hip hop", id="already_normalized"),
            pytest.param("Café Soul", "cafe soul", id="unidecode_accents"),
            pytest.param("r&b", "r&b", id="ampersand_preserved"),
            pytest.param("  funk  ", "funk", id="extra_whitespace"),
        ],
    )
    def test__nominal(self, genre: str, expected: str) -> None:
        assert normalize_genre_key(genre) == expected


class TestDeduplicateGenreDict:
    def test__merges_hyphen_variants(self) -> None:
        result = deduplicate_genre_dict({"hip-hop": 0.4, "hip hop": 0.3})
        assert result == {"hip hop": 0.7}

    def test__expands_slash_compound(self) -> None:
        result = deduplicate_genre_dict({"hip hop/rap": 0.5})
        assert result == {"hip hop": 0.5, "rap": 0.5}

    def test__expands_slash_compound_and_deduplicates(self) -> None:
        result = deduplicate_genre_dict({"hip hop": 0.3, "hip hop/rap": 0.4})
        assert result == {"hip hop": 0.7, "rap": 0.4}

    def test__expands_slash_compound_with_hyphen(self) -> None:
        result = deduplicate_genre_dict({"hip-hop/rap": 0.5, "rap/hip-hop": 0.3})
        assert result == {"hip hop": 0.8, "rap": 0.8}

    def test__merges_plural_variant(self) -> None:
        result = deduplicate_genre_dict({"afrobeats": 0.6, "afrobeat": 0.2})
        assert result == {"afrobeat": 0.8}

    def test__caps_weight_at_one(self) -> None:
        result = deduplicate_genre_dict({"afrobeats": 0.8, "afrobeat": 0.6})
        assert result == {"afrobeat": 1.0}

    def test__preserves_distinct_genres(self) -> None:
        result = deduplicate_genre_dict({"indie rock": 0.8, "electronic": 0.4})
        assert result == {"indie rock": 0.8, "electronic": 0.4}

    def test__empty_dict(self) -> None:
        assert deduplicate_genre_dict({}) == {}
