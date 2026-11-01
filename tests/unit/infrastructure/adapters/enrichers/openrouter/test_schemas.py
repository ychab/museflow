import pytest

from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.enums import EnrichField
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
        assert item.required == ["track_index", "genre_macro", "genre_meso", "genre_micro", "moods", "locales"]
        assert item.additionalProperties is False
        assert item.properties["track_index"].type == "integer"
        assert item.properties["locales"].type == "array"

    def test__all_fields__genre_tiers_and_moods_are_enums(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        moods_items = item.properties["moods"].items
        assert moods_items is not None
        assert item.properties["genre_macro"].enum == [g.value for g in GENRE_MACRO_TAGS]
        assert item.properties["genre_meso"].enum == [g.value for g in GENRE_MESO_TAGS]
        assert moods_items.enum == [m.value for m in MoodTag]

    def test__all_fields__genre_micro_is_nullable(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        assert item.properties["genre_micro"] == JsonSchemaProperty.enum_string(
            [g.value for g in GENRE_MICRO_TAGS], nullable=True
        )

    @pytest.mark.parametrize("item", [frozenset({EnrichField.GENRE})], indirect=True)
    def test__locales_not_requested__absent_from_schema(self, item: JsonSchemaProperty) -> None:
        assert item.properties is not None
        assert list(item.properties) == ["track_index", "genre_macro", "genre_meso", "genre_micro"]
        assert item.required == ["track_index", "genre_macro", "genre_meso", "genre_micro"]


class TestEnrichedTrack:
    @pytest.mark.parametrize(
        ("tiers", "expected"),
        [
            pytest.param(
                {"genre_macro": "hip-hop", "genre_meso": "rap", "genre_micro": "afro rap"},
                ["hip-hop", "rap", "afro rap"],
                id="three_tiers",
            ),
            pytest.param(
                {"genre_macro": "hip-hop", "genre_meso": "rap", "genre_micro": None},
                ["hip-hop", "rap"],
                id="no_micro",
            ),
            pytest.param({}, [], id="genre_not_requested"),
        ],
    )
    def test__genres__tiers_broadest_first(self, tiers: dict[str, str | None], expected: list[str]) -> None:
        item = EnrichedTrack.model_validate({"track_index": 0, **tiers})

        assert item.genres == expected

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
