import logging
import random
import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import Final

from museflow.application.inputs.explore import ExploreArtistsConfigInput
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.discovery import DiscoveryService
from museflow.application.services.llm_usage import LLMUsageService
from museflow.application.utils.discovery import filter_by_artist
from museflow.application.utils.discovery import rank_favourite_artists
from museflow.application.utils.discovery import select_tracks
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.utils.text import normalize_text
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.stats import ArtistStats
from museflow.domain.value_objects.taste import TrackPicked

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ExploreArtistsAttemptReport:
    attempt: int = 0
    artists: int = 0  # favourite artists searched
    candidates: int = 0  # their catalogue tracks the user does not know, offered to the advisor
    tracks_picked: int = 0  # among the candidates


@dataclass(frozen=True, kw_only=True)
class ExploreArtistsResult:
    playlist: Playlist | None
    reports: list[ExploreArtistsAttemptReport]
    tracks: list[Track]


class ExploreArtistsUseCase:
    """Use case for the tracks the user missed from the artists they already love."""

    _PLAYLIST_NAME: Final[str] = "Explore"
    # The user's best-rated tracks of an artist shown to the advisor: what they love in them
    _LIKED_TRACKS_PER_ARTIST: Final[int] = 5

    def __init__(
        self,
        uow: UnitOfWorkPort,
        provider_library: ProviderLibraryPort,
        advisor: AdvisorPort,
    ) -> None:
        self._uow = uow
        self._advisor = advisor
        # Application services built from the ports above, not ports: never injected
        self._discovery = DiscoveryService(uow=uow, provider_library=provider_library)
        self._llm_usage = LLMUsageService(uow=uow)

    async def create_playlist(self, user: User, config: ExploreArtistsConfigInput) -> ExploreArtistsResult:
        """Creates a playlist of the catalogue tracks the user does not know, from their favourite artists.

        The favourites come from the user's data, with no advisor call: ratings first, then plays. Each round takes
        the next few of them, searches their whole catalogue, then asks the advisor to pick among their tracks the
        user does not know, guided by the tracks the user rated highest. Stops once `playlist_limit` tracks are kept
        after the per-artist cap, after `max_attempts` rounds, or once no favourite is left.

        Raises:
            DiscoveryTrackNoNewError: If no new tracks are found after all rounds.
        """
        async with self._uow as uow:
            blacklist = await uow.blacklist.get(user.id)
            liked_tracks = await uow.tracks.get_list(
                user_id=user.id,
                min_score=config.liked_tracks_score_threshold,
                limit=config.liked_tracks_limit,
            )
            artist_stats = await uow.tracks.get_artist_stats(user_id=user.id)
        artists = self._draw_artists(artist_stats, blacklist, config)

        # What the advisor spent is saved whatever the outcome: a failed run was billed too.
        playlist_id: uuid.UUID | None = None
        try:
            result = await self._explore(user, config, artists, blacklist, liked_tracks)
            playlist_id = result.playlist.id if result.playlist else None
        finally:
            await self._llm_usage.record(
                user_id=user.id,
                operation=LLMOperation.EXPLORE,
                usages=self._advisor.usages,
                playlist_id=playlist_id,
            )
        return result

    async def _explore(
        self,
        user: User,
        config: ExploreArtistsConfigInput,
        artists: list[str],
        blacklist: UserBlacklist,
        liked_tracks: list[Track],
    ) -> ExploreArtistsResult:
        tracks_picked: list[TrackPicked] = []
        # What the playlist would hold now: the loop stops on it, so a round cut by the per-artist cap needs another.
        tracks: list[Track] = []
        reports: list[ExploreArtistsAttemptReport] = []

        for attempt in range(1, config.max_attempts + 1):
            start = (attempt - 1) * config.artists_per_attempt
            artists_now = artists[start : start + config.artists_per_attempt]
            if not artists_now:
                logger.info(f"Attempt {attempt}/{config.max_attempts}: no favourite artist left, stopping")
                break

            logger.info(f"Attempt {attempt}/{config.max_attempts}")
            for artist in artists_now:
                logger.debug(f"Favourite artist '{artist}'")
            candidates = await self._discovery.get_unknown_artist_tracks(
                user=user,
                artists=artists_now,
                # Their best-known tracks are the user's already: the catalogue search reaches the others.
                artists_deep=set(artists_now),
                blacklist=blacklist,
                fingerprints_kept={tp.track.fingerprint for tp in tracks_picked},
                artist_tracks_pages=config.catalogue_tracks_pages,
                catalogue_tracks_pages=config.catalogue_tracks_pages,
                concurrency=config.artist_tracks_concurrency,
            )

            tracks_picked_now: list[TrackPicked] = []
            if candidates:
                tracks_picked_now = await self._advisor.pick_exploration_tracks(
                    candidates=candidates,
                    liked_tracks=self._group_liked_tracks(liked_tracks, artists=list(candidates)),
                    tracks_limit=config.picks_limit,
                    max_tracks_per_artist=config.max_tracks_per_artist,
                    prompt=config.prompt,
                )
                for track_picked in tracks_picked_now:
                    logger.debug(f"Picked ({track_picked.score:.2f}): '{track_picked.track}'")

            reports.append(
                ExploreArtistsAttemptReport(
                    attempt=attempt,
                    artists=len(artists_now),
                    candidates=sum(len(tracks) for tracks in candidates.values()),
                    tracks_picked=len(tracks_picked_now),
                )
            )

            tracks_picked.extend(tracks_picked_now)
            tracks = select_tracks(
                tracks_picked=tracks_picked,
                max_tracks_per_artist=config.max_tracks_per_artist,
                playlist_limit=config.playlist_limit,
            )
            logger.info(
                f"Attempt {attempt}/{config.max_attempts}: +{len(tracks_picked_now)} tracks "
                f"(total: {len(tracks_picked)}, {len(tracks)} kept)",
                extra={"attempt": attempt, "total": len(tracks_picked), "kept": len(tracks)},
            )
            if len(tracks) >= config.playlist_limit:
                break

        if not tracks:
            raise DiscoveryTrackNoNewError()

        if len(tracks) < config.playlist_limit:
            logger.warning(
                f"playlist_limit not reached ({len(tracks)}/{config.playlist_limit}) after {len(reports)} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_limit, "attempts": len(reports)},
            )

        if config.dry_run:
            logger.info("Dry-run mode: skipping playlist creation.")
            return ExploreArtistsResult(playlist=None, reports=reports, tracks=tracks)

        name = config.title or f"[MF] - {self._PLAYLIST_NAME} - {datetime.now(UTC).isoformat(timespec='seconds')}"
        playlist = await self._discovery.create_playlist(
            name=name,
            type=PlaylistType.EXPLORE,
            tracks=tracks,
            prompt=config.prompt,
        )
        return ExploreArtistsResult(playlist=playlist, reports=reports, tracks=playlist.tracks)

    @staticmethod
    def _draw_artists(
        artist_stats: list[ArtistStats],
        blacklist: UserBlacklist,
        config: ExploreArtistsConfigInput,
    ) -> list[str]:
        """Returns the user's best favourite artists, not blacklisted, in a random order.

        Shuffled so that two runs start with other artists: the rounds take them in this order.
        """
        artists = [
            artist
            for artist in rank_favourite_artists(artist_stats, confidence=config.ratings_confidence)
            if normalize_text(artist) not in blacklist.artist_fingerprints
        ][: config.artists_limit]
        random.shuffle(artists)
        logger.info(f"Favourite artists drawn: {len(artists)}", extra={"artists": len(artists)})
        return artists

    @classmethod
    def _group_liked_tracks(cls, liked_tracks: list[Track], artists: list[str]) -> dict[str, list[Track]]:
        """Returns the user's best-rated tracks crediting each artist, best first, for the artists with any."""
        liked_by_artist: dict[str, list[Track]] = {}
        for artist in artists:
            liked = filter_by_artist(artist=artist, tracks=liked_tracks, log_enabled=False)
            if liked:
                liked_by_artist[artist] = liked[: cls._LIKED_TRACKS_PER_ARTIST]
        return liked_by_artist
