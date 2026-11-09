import pytest

from museflow.domain.utils.text import normalize_numbers
from museflow.domain.utils.text import normalize_text
from museflow.domain.utils.text import strip_brackets
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


class TestStripBrackets:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("Neon Harbor", "Neon Harbor", id="untouched"),
            pytest.param("Neon Harbor (Nightfall)", "Neon Harbor", id="parenthesis"),
            pytest.param("Neon [Slowed] Harbor", "Neon Harbor", id="inner-square"),
            pytest.param("(Intro)", "(Intro)", id="only-brackets"),
        ],
    )
    def test__nominal(self, text: str, expected: str) -> None:
        assert strip_brackets(text) == expected


class TestNormalizeNumbers:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("one night", "1 night", id="english"),
            pytest.param("une nuit sur deux", "1 nuit sur 2", id="french"),
            pytest.param("2 moons", "2 moons", id="digits-untouched"),
            pytest.param("someone", "someone", id="inside-word-untouched"),
        ],
    )
    def test__nominal(self, text: str, expected: str) -> None:
        assert normalize_numbers(text) == expected


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
