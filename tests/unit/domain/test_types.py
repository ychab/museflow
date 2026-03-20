import pytest

from museflow.domain.types import TrackSource


class TestTrackSource:
    @pytest.mark.parametrize(
        ("kwargs", "expected_flag"),
        [
            ({"top": True}, TrackSource.TOP),
            ({"saved": True}, TrackSource.SAVED),
            ({"playlist": True}, TrackSource.PLAYLIST),
            ({"history": True}, TrackSource.HISTORY),
        ],
    )
    def test__from_flags__single_flags(self, kwargs: dict[str, bool], expected_flag: TrackSource) -> None:
        assert TrackSource.from_flags(**kwargs) == expected_flag

    @pytest.mark.parametrize(
        ("kwargs", "expected_flag"),
        [
            (
                {"top": True, "saved": True},
                TrackSource.TOP | TrackSource.SAVED,
            ),
            (
                {"playlist": True, "history": True, "top": True},
                TrackSource.TOP | TrackSource.PLAYLIST | TrackSource.HISTORY,
            ),
        ],
    )
    def test__from_flags__combined_flags(self, kwargs: dict[str, bool], expected_flag: TrackSource) -> None:
        assert TrackSource.from_flags(**kwargs) == expected_flag

    @pytest.mark.parametrize(
        "kwargs",
        [
            ({}),
            ({"top": False}),
            ({"saved": None, "playlist": False}),
            ({"top": False, "saved": False, "playlist": False, "history": False}),
        ],
    )
    def test__from_flags__none(self, kwargs: dict[str, bool | None]) -> None:
        assert TrackSource.from_flags(**kwargs) is None

    @pytest.mark.parametrize(
        ("kwargs", "expected_flag"),
        [
            ({"top": True, "saved": False}, TrackSource.TOP),
            ({"playlist": True, "history": None}, TrackSource.PLAYLIST),
        ],
    )
    def test__from_flags__combine_ignores_false(
        self,
        kwargs: dict[str, bool | None],
        expected_flag: TrackSource,
    ) -> None:
        assert TrackSource.from_flags(**kwargs) == expected_flag
