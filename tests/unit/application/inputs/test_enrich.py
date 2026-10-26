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
        ],
    )
    def test__locales__sanitized(self, data: dict[str, object], expected: list[str] | None) -> None:
        entry = EnrichEntryInput.model_validate({"fingerprint": "abc", **data})

        assert entry.locales == expected
