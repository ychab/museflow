import pytest

from museflow.domain.utils.text import normalize_text


class TestNormalizeText:
    def test__empty(self) -> None:
        assert normalize_text("") == ""

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
