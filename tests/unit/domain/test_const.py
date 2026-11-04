from museflow.domain.const import GENRE_MACRO_TAGS
from museflow.domain.const import GENRE_MESO_TAGS
from museflow.domain.const import GENRE_MICRO_TAGS
from museflow.domain.enums import GenreTag
from museflow.domain.enums import MoodTag


class TestTagVocabulary:
    """The taste profile weights are keyed by tag alone: a tag listed twice would merge two meanings in one weight."""

    def test__genres_and_moods__disjoint(self) -> None:
        assert {t.value for t in GenreTag} & {m.value for m in MoodTag} == set()

    def test__genre_tiers__disjoint_and_complete(self) -> None:
        tiers = [*GENRE_MACRO_TAGS, *GENRE_MESO_TAGS, *GENRE_MICRO_TAGS]

        assert len(tiers) == len(set(tiers))
        assert set(tiers) == set(GenreTag)
