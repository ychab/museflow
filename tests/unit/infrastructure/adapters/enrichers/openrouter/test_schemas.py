import pytest

from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.enrichers.openrouter.schemas import EnrichedTrack
from museflow.infrastructure.adapters.enrichers.openrouter.schemas import build_enrichment_schema


class TestBuildEnrichmentSchema:
    @pytest.fixture
    def item(self, request: pytest.FixtureRequest) -> JsonSchemaProperty:
        fields: frozenset[EnrichField] = getattr(request, "param", frozenset(EnrichField))
        root = build_enrichment_schema(fields)
        assert root.properties is not None
        items = root.properties["enriched_tracks"].items
        assert items is not None
        return items

    def test__all_fields__strict_and_required(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        assert item.required == ["track_index", "genres", "moods", "locales"]
        assert item.additionalProperties is False
        assert item.properties["track_index"].type == "integer"
        assert item.properties["locales"].type == "array"

    def test__all_fields__genres_and_moods_items_are_enums(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        genres_items = item.properties["genres"].items
        moods_items = item.properties["moods"].items
        assert genres_items is not None
        assert moods_items is not None
        assert genres_items.enum == [g.value for g in GenreTag]
        assert moods_items.enum == [m.value for m in MoodTag]

    @pytest.mark.parametrize("item", [frozenset({EnrichField.GENRE})], indirect=True)
    def test__locales_not_requested__absent_from_schema(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        assert list(item.properties) == ["track_index", "genres"]
        assert item.required == ["track_index", "genres"]


class TestEnrichedTrack:
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
        item = EnrichedTrack.model_validate({"track_index": 0, "locales": raw})

        assert item.locales == expected
