from typing import Any

from pydantic import ValidationError

import pytest

from museflow.application.inputs.taste import BuildTasteProfileJobInput


class TestBuildTasteProfileJobInput:
    @pytest.mark.parametrize(
        ("data", "expected"),
        [
            ({"title": "Soirées d'hiver", "name": ""}, "soirees-d-hiver"),
            ({"title": "Soirées d'hiver", "name": "winter"}, "winter"),
            ({"title": "!!!", "name": "winter"}, "winter"),
        ],
    )
    def test__name(self, data: dict[str, Any], expected: str) -> None:
        job_in = BuildTasteProfileJobInput.model_validate(data)

        assert job_in.name == expected

    @pytest.mark.parametrize(
        ("data", "match"),
        [
            ({"title": "!!!"}, "needs a letter or a digit"),
            ({"title": "Winter", "name": "not a slug"}, "string_pattern_mismatch"),
            ({"title": "", "name": "winter"}, "string_too_short"),
            ({"title": 42}, "string_type"),
        ],
    )
    def test__invalid(self, data: dict[str, Any], match: str) -> None:
        with pytest.raises(ValidationError, match=match):
            BuildTasteProfileJobInput.model_validate(data)
