import pytest

from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.entities.track import Track
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag
from museflow.infrastructure.entrypoints.cli.dependencies import get_enricher
from museflow.infrastructure.entrypoints.cli.dependencies import get_profiler

from tests.unit.factories.entities.track import TrackFactory

# One model per family next to the defaults (None): each must accept the real response schemas
_SONNET = "anthropic/claude-sonnet-4.5"
_GPT = "openai/gpt-5-mini"


@pytest.fixture
def tracks() -> list[Track]:
    return [
        TrackFactory.build(name="Bohemian Rhapsody", artists=["Queen"]),
        TrackFactory.build(name="Lose Yourself", artists=["Eminem"]),
    ]


@pytest.mark.openrouter_live
class TestOpenRouterSchemasLive:
    """
    Live compatibility check of the real response schemas across model families, through the real dependencies (so the
    model and ZDR checks run too).

    Warning:
        These tests spend real money (a few cents in all). They are NOT run by default.

    To run:
        OPENROUTER_API_KEY=<KEY> uv run pytest ./tests/integration/live/openrouter --openrouter-live --no-cov
    """

    @pytest.mark.parametrize("model", [None, _SONNET, _GPT])
    async def test__enricher(self, model: str | None, tracks: list[Track]) -> None:
        async with get_enricher(model=model) as enricher:
            enrichments = await enricher.enrich_tracks(tracks[:1], fields=frozenset(EnrichField))

        assert len(enrichments) == 1
        genres = enrichments[0].genres
        assert genres[0] in GENRE_MACRO_TAGS
        assert genres[1] in GENRE_MESO_TAGS
        assert all(isinstance(mood, MoodTag) for mood in enrichments[0].moods)

    @pytest.mark.parametrize(
        "model", [None, "google/gemini-3.5-flash", "google/gemini-3.1-pro-preview", _SONNET, _GPT]
    )
    async def test__profiler_segment(self, model: str | None, tracks: list[Track]) -> None:
        async with get_profiler(segment_model=model) as profiler:
            segment = await profiler.build_profile_segment(tracks)

        assert segment["core_identity"]
        valid_keys = {t.value for t in GenreTag} | {m.value for m in MoodTag}
        assert set(segment["core_identity"]) <= valid_keys
