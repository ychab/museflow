from pydantic import ValidationError

import pytest

from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_ARTISTS_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DISCOVERY_PICKS_SCHEMA
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedArtist
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty


class TestSuggestedArtist:
    def test__parse__empty_name(self) -> None:
        with pytest.raises(ValidationError):
            SuggestedArtist.model_validate({"name": "", "sound": "Warm brass", "score": 0.5})


class TestDiscoverySchemas:
    @pytest.mark.parametrize(
        "schema",
        [
            pytest.param(DISCOVERY_ARTISTS_SCHEMA, id="artists"),
            pytest.param(DISCOVERY_PICKS_SCHEMA, id="picks"),
        ],
    )
    def test__strict__all_properties_required(self, schema: JsonSchemaProperty) -> None:
        assert schema.properties is not None
        assert schema.required == list(schema.properties)
        assert schema.additionalProperties is False
