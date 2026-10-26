import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput


class TestDiscoverTasteConfigInput:
    @pytest.mark.parametrize("max_attempts", [0, -1])
    def test__max_attempts__below_one(self, max_attempts: int) -> None:
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            DiscoverTasteConfigInput(max_attempts=max_attempts)
