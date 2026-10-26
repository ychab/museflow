import pytest

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty
from museflow.infrastructure.adapters.enrichers.gemini.schemas import GeminiEnrichedTrack
from museflow.infrastructure.adapters.enrichers.gemini.schemas import build_enrichment_config


class TestBuildEnrichmentConfig:
    @pytest.fixture
    def item(self, request: pytest.FixtureRequest) -> GeminiSchemaProperty:
        fields: frozenset[EnrichField] = getattr(request, "param", frozenset(EnrichField))
        root = build_enrichment_config(fields).responseSchema
        assert root.properties is not None
        items = root.properties["enriched_tracks"].items
        assert items is not None
        return items

    def test__all_fields__locales_required(self, item: GeminiSchemaProperty) -> None:
        assert item.properties is not None
        assert item.required is not None
        assert "locales" in item.properties
        assert "locales" in item.required
        assert item.properties["locales"].type == "array"

    def test__all_fields__genres_and_moods_items_are_enums(self, item: GeminiSchemaProperty) -> None:
        assert item.properties is not None
        genres_items = item.properties["genres"].items
        moods_items = item.properties["moods"].items
        assert genres_items is not None
        assert moods_items is not None
        assert genres_items.enum == [g.value for g in GenreTag]
        assert moods_items.enum == [m.value for m in MoodTag]

    @pytest.mark.parametrize("item", [frozenset({EnrichField.GENRE})], indirect=True)
    def test__locales_not_requested__absent_from_schema(self, item: GeminiSchemaProperty) -> None:
        assert item.properties is not None
        assert item.required is not None
        assert "locales" not in item.properties
        assert "locales" not in item.required


class TestGeminiEnrichedTrack:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (["FR", "en", "fr"], ["fr", "en"]),
            (["fra", 3, "en"], ["en"]),
            (["fra"], None),
            ([], []),
            (None, None),
            ("fr", None),
        ],
    )
    def test__locales__sanitized(self, raw: object, expected: list[str] | None) -> None:
        item = GeminiEnrichedTrack.model_validate({"track_index": 0, "locales": raw})

        assert item.locales == expected
