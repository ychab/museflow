import asyncio
import logging
from unittest import mock

import pytest

from museflow.application.services.discovery import DiscoveryService
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import ProviderRateLimitExceededError
from museflow.domain.exceptions import ProviderSearchQueryInvalidError
from museflow.domain.value_objects.blacklist import UserBlacklist

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.blacklist import BlacklistedTrackFactory
from tests.unit.factories.entities.track import TrackFactory


@pytest.fixture
def service(mock_uow: mock.AsyncMock, mock_provider_library: mock.AsyncMock) -> DiscoveryService:
    return DiscoveryService(uow=mock_uow, provider_library=mock_provider_library)


class TestGetUnknownArtistTracks:
    @pytest.fixture(autouse=True)
    def nothing_known(self, mock_track_repository: mock.AsyncMock) -> None:
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(is_known=mock.Mock(return_value=False))
        mock_track_repository.get_list.return_value = []

    async def test__candidates__filtered(
        self,
        service: DiscoveryService,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        """Only the unknown, not blacklisted, not yet kept tracks crediting the asked artist are offered, each once."""
        first, second, third = "The Fictional Band", "Another Band", "Nova"
        kept = TrackFactory.build(artists=[first])
        close_name = TrackFactory.build(artists=[f"{first}lee"])
        blacklisted_artist = TrackFactory.build(artists=[first, "A Blacklisted Band"])
        blacklisted_track = TrackFactory.build(artists=[first])
        known = TrackFactory.build(artists=[first])
        kept_earlier = TrackFactory.build(artists=[first])
        # Credits both artists: offered under the first one only.
        shared = TrackFactory.build(artists=[first, second])
        only_known = TrackFactory.build(artists=[second])
        mock_provider_library.search_artist_tracks.side_effect = [
            [kept, close_name, blacklisted_artist, blacklisted_track, known, kept_earlier, shared],
            [shared, only_known],
            # Only an artist with a close name: nothing of the asked one.
            [TrackFactory.build(artists=[f"{third} Jr"])],
        ]
        blacklist = UserBlacklist(
            artists=[BlacklistedArtistFactory.build(artist_name="A Blacklisted Band", fingerprint="")],
            tracks=[BlacklistedTrackFactory.build(fingerprint=blacklisted_track.fingerprint)],
        )
        mock_track_repository.get_known_identifiers.return_value = mock.Mock(
            is_known=mock.Mock(side_effect=lambda track: track in (known, only_known))
        )

        candidates = await service.get_unknown_artist_tracks(
            user=user,
            artists=[first, second, third],
            artists_deep=set(),
            blacklist=blacklist,
            fingerprints_kept={kept_earlier.fingerprint},
            artist_tracks_pages=2,
            catalogue_tracks_pages=10,
            concurrency=4,
        )

        # The second and third artists are left without any track: not offered at all.
        assert candidates == {first: [kept, shared]}
        mock_provider_library.search_artist_tracks.assert_any_await(artist=first, max_pages=2, log_enabled=False)

    async def test__artists_deep__catalogue_searched(
        self,
        service: DiscoveryService,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        """An artist searched deep gets the catalogue search, and only their studio tracks: no live, no medley."""
        deep, plain = "The Fictional Band", "Another Band"
        track_deep = TrackFactory.build(name="Neon Harbor", album_name="Night Drive", artists=[deep])
        live_deep = TrackFactory.build(name="Neon Harbor - Live", artists=[deep])
        medley_deep = TrackFactory.build(name="Glass Rain / Paper Moon / Neon Harbor", artists=[deep])
        track_plain = TrackFactory.build(name="Glass Rain (Live)", artists=[plain])
        mock_provider_library.search_artist_catalogue.return_value = [track_deep, live_deep, medley_deep]
        mock_provider_library.search_artist_tracks.return_value = [track_plain]

        candidates = await service.get_unknown_artist_tracks(
            user=user,
            artists=[deep, plain],
            artists_deep={deep},
            blacklist=UserBlacklist(),
            fingerprints_kept=set(),
            artist_tracks_pages=2,
            catalogue_tracks_pages=10,
            concurrency=4,
        )

        assert candidates == {deep: [track_deep], plain: [track_plain]}
        mock_provider_library.search_artist_catalogue.assert_awaited_once_with(artist=deep, max_pages=10)
        mock_provider_library.search_artist_tracks.assert_awaited_once_with(
            artist=plain, max_pages=2, log_enabled=False
        )

    async def test__search_query_invalid__artist_skipped(
        self,
        service: DiscoveryService,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        malformed, valid = "Caf\x00", "The Fictional Band"
        track = TrackFactory.build(artists=[valid])
        mock_provider_library.search_artist_tracks.side_effect = [ProviderSearchQueryInvalidError(), [track]]

        with caplog.at_level(logging.WARNING):
            candidates = await service.get_unknown_artist_tracks(
                user=user,
                artists=[malformed, valid],
                artists_deep=set(),
                blacklist=UserBlacklist(),
                fingerprints_kept=set(),
                artist_tracks_pages=2,
                catalogue_tracks_pages=10,
                concurrency=4,
            )

        assert candidates == {valid: [track]}
        assert f"Artist skipped, its search query was rejected: '{malformed}'" in caplog.text

    async def test__searches__concurrent__bounded__artists_order_kept(
        self,
        service: DiscoveryService,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        """At most `concurrency` searches run at once; a shared track stays with the first artist."""
        artists = [f"Band {i}" for i in range(5)]
        shared = TrackFactory.build(artists=[artists[0], artists[1]])
        tracks = {artist: [TrackFactory.build(artists=[artist])] for artist in artists}
        tracks[artists[0]].append(shared)
        tracks[artists[1]].append(shared)

        # The first artists finish last: the candidates must still follow the artists' order.
        yields = {artist: len(artists) - i for i, artist in enumerate(artists)}
        running = running_max = 0

        async def _search(artist: str, **_: object) -> list[Track]:
            nonlocal running, running_max
            running += 1
            running_max = max(running_max, running)
            for _turn in range(yields[artist]):
                await asyncio.sleep(0)
            running -= 1
            return tracks[artist]

        mock_provider_library.search_artist_tracks.side_effect = _search

        candidates = await service.get_unknown_artist_tracks(
            user=user,
            artists=artists,
            artists_deep=set(),
            blacklist=UserBlacklist(),
            fingerprints_kept=set(),
            artist_tracks_pages=2,
            catalogue_tracks_pages=10,
            concurrency=2,
        )

        assert running_max == 2
        assert list(candidates) == artists
        assert candidates[artists[0]] == tracks[artists[0]]
        assert candidates[artists[1]] == tracks[artists[1]][:1]

    async def test__search_fails__other_searches_cancelled(
        self,
        service: DiscoveryService,
        user: User,
        mock_uow: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        failing, pending = "The Fictional Band", "Another Band"
        never: asyncio.Future[list[Track]] = asyncio.get_running_loop().create_future()

        async def _search(artist: str, **_: object) -> list[Track]:
            if artist == failing:
                raise ProviderRateLimitExceededError("Spotify rate limit")
            return await never

        mock_provider_library.search_artist_tracks.side_effect = _search

        with pytest.raises(ProviderRateLimitExceededError):
            await service.get_unknown_artist_tracks(
                user=user,
                artists=[failing, pending],
                artists_deep=set(),
                blacklist=UserBlacklist(),
                fingerprints_kept=set(),
                artist_tracks_pages=2,
                catalogue_tracks_pages=10,
                concurrency=4,
            )

        assert never.cancelled()


class TestCreateDiscoveryPlaylist:
    async def test__remote_creation_fails__nothing_written(
        self,
        service: DiscoveryService,
        mock_uow: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        mock_provider_library.create_playlist.side_effect = ProviderRateLimitExceededError("Spotify rate limit")

        with pytest.raises(ProviderRateLimitExceededError):
            await service.create_playlist(
                name="Friday night",
                type=PlaylistType.DISCOVERY,
                tracks=TrackFactory.batch(2),
            )

        mock_uow.__aenter__.assert_not_awaited()
        mock_track_repository.bulk_upsert.assert_not_awaited()
        mock_playlist_repository.create.assert_not_awaited()
