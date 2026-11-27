import pytest

from museflow.domain.utils.text import normalize_text
from museflow.domain.utils.text import slugify
from museflow.domain.utils.text import strip_control_chars
from museflow.domain.utils.text import unidecode_lower_text
from museflow.domain.utils.text import validate_locales


class TestUnidecodeLower:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("variété française", "variete francaise", id="unidecode"),
            pytest.param("PoP", "pop", id="lowercase"),
        ],
    )
    def test__nominal(self, text: str, expected: str) -> None:
        assert unidecode_lower_text(text) == expected


class TestSlugify:
    @pytest.mark.parametrize(
        ("text", "max_length", "expected"),
        [
            pytest.param("Soirées d'hiver", 64, "soirees-d-hiver", id="accents_apostrophe"),
            pytest.param("  Late night / Winter 2025!  ", 64, "late-night-winter-2025", id="punctuation_spaces"),
            pytest.param("main", 64, "main", id="already_a_slug"),
            pytest.param("🎧 ♪", 64, "", id="no_letter_nor_digit"),
            pytest.param("abc def", 4, "abc", id="cut_at_a_hyphen"),
        ],
    )
    def test__nominal(self, text: str, max_length: int, expected: str) -> None:
        assert slugify(text, max_length=max_length) == expected


class TestStripControlChars:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("Café", "Café", id="untouched"),
            pytest.param("Caf\x00\x19", "Caf", id="trailing"),
            pytest.param("The\x1bFictional\tBand", "The Fictional Band", id="inner"),
            pytest.param("\x00\x7f\x85", "", id="only-control"),
        ],
    )
    def test__nominal(self, text: str, expected: str) -> None:
        assert strip_control_chars(text) == expected


class TestNormalizeText:
    @pytest.mark.parametrize(
        ("text", "expected_str"),
        [
            pytest.param("Soldi famiglia (feat. Sfera Ebbasta)", "soldi famiglia", id="feat.-parenthesis"),
            pytest.param("Cosmos - feat. PLK", "cosmos", id="feat.-hyphen"),
            pytest.param("Condo Music (Feat. Wicced)", "condo music", id="feat.-parenthesis-capitalize"),
            pytest.param("Mi Luz (ft. Rels B)", "mi luz", id="ft.-parenthesis"),
            pytest.param("Mi Luz - ft. Rels B", "mi luz", id="ft.-hyphen"),
            pytest.param("Anacaona (Remastered 2025)", "anacaona", id="remaster-parenthesis"),
            pytest.param("Anacaona - Remastered 2025", "anacaona", id="remaster-hyphen"),
            pytest.param("Vale la Pena (Live)", "vale la pena", id="live-parenthesis"),
            pytest.param("Vale la Pena - Live", "vale la pena", id="live-hyphen"),
            pytest.param("Iboru Iboya (Edit)", "iboru iboya", id="edit-parenthesis"),
            pytest.param("J'en rêve encore - Radio Edit", "jen reve encore", id="edit-hyphen"),
            pytest.param(
                "Somebody That I Used To Know (Glee Cast Version)",
                "somebody that i used to know",
                id="version-parenthesis",
            ),
            pytest.param("Fabricando Fantasías - Salsa Version", "fabricando fantasias", id="version-hyphen"),
        ],
    )
    def test__nominal(self, text: str, expected_str: str) -> None:
        assert normalize_text(text) == expected_str


class TestValidateLocales:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param(["FR", "en", "fr"], ["fr", "en"], id="normalized-deduplicated"),
            pytest.param(["fra", 3, "en"], ["en"], id="invalid-dropped"),
            pytest.param([], [], id="empty-is-an-answer"),
            pytest.param(["fra"], None, id="only-invalid"),
            pytest.param([None], None, id="only-null"),
            pytest.param("fr", None, id="not-a-list"),
            pytest.param(None, None, id="none"),
        ],
    )
    def test__nominal(self, value: object, expected: list[str] | None) -> None:
        assert validate_locales(value) == expected
