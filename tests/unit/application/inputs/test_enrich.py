import pytest

from museflow.application.inputs.enrich import EnrichEntryInput


class TestEnrichEntryInput:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"locales": ["fr", "EN", "xyz"]}, ["fr", "en"]),
            ({"locales": ["xyz"]}, None),
            ({"locales": []}, []),
            ({"locales": "fr"}, None),
            ({}, None),
            ({"locale": "fr"}, ["fr"]),
            ({"locale": "FR"}, ["fr"]),
            ({"locale": "french"}, None),
            ({"locale": None}, None),
            ({"locale": "fr", "locales": ["en", "de"]}, ["en", "de"]),
            ({"locale": "fr", "locales": []}, []),
        ],
    )
    def test__locales__legacy_and_current_keys(self, data: dict[str, object], expected: list[str] | None) -> None:
        entry = EnrichEntryInput.model_validate({"fingerprint": "abc", **data})

        assert entry.locales == expected

    def test__non_dict_input__passes_through(self) -> None:
        entry = EnrichEntryInput.model_validate(EnrichEntryInput(fingerprint="abc"))

        assert entry.locales is None
