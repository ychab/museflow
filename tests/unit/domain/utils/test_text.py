from museflow.domain.utils.text import normalize_text


class TestNormalizeText:
    def test__empty(self) -> None:
        assert normalize_text("") == ""
