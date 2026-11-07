import pytest

from museflow.application.inputs.enrich import EnrichmentEntryInput


class TestEnrichmentEntryInput:
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
        entry = EnrichmentEntryInput.model_validate({"fingerprint": "abc", **data})

        assert entry.locales == expected
