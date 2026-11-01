from collections.abc import Iterator
from itertools import combinations

import pytest

from museflow.domain.enums import EnrichField
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_STRATEGY_SCHEMA
from museflow.infrastructure.adapters.common.llm.json_schema import MAX_ENUM_VALUES
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.enrichers.openrouter.schemas import build_enrichment_schema
from museflow.infrastructure.adapters.profilers.openrouter.schemas import TASTE_PROFILE_SCHEMA


def _walk(node: JsonSchemaProperty) -> Iterator[JsonSchemaProperty]:
    yield node
    children = [*(node.anyOf or []), *(node.properties or {}).values()]
    if node.items:
        children.append(node.items)
    for child in children:
        yield from _walk(child)


_SCHEMAS = [
    *(
        pytest.param(build_enrichment_schema(frozenset(fields)), id=f"enricher-{'-'.join(sorted(fields))}")
        for size in range(1, len(EnrichField) + 1)
        for fields in combinations(EnrichField, size)
    ),
    pytest.param(TASTE_PROFILE_SCHEMA, id="profiler"),
    pytest.param(DISCOVERY_STRATEGY_SCHEMA, id="advisor"),
]


@pytest.mark.parametrize("schema", _SCHEMAS)
class TestSchemaPortability:
    """The response schemas stay within what every model family accepts (see `JsonSchemaProperty`)."""

    def test__enum__max_values(self, schema: JsonSchemaProperty) -> None:
        assert all(len(node.enum) <= MAX_ENUM_VALUES for node in _walk(schema) if node.enum)

    def test__enum__single_type(self, schema: JsonSchemaProperty) -> None:
        assert all(node.type == "string" for node in _walk(schema) if node.enum)

    def test__any_of__nullable_only(self, schema: JsonSchemaProperty) -> None:
        for node in _walk(schema):
            if node.anyOf:
                assert len(node.anyOf) == 2
                assert node.anyOf[0].type != "null"
                assert node.anyOf[1] == JsonSchemaProperty(type="null")
