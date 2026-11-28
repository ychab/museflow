import logging
import uuid
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow.application.inputs.discovery import CreateDiscoveryPlaylistConfigInput
from museflow.application.outputs.progress import CandidatesFound
from museflow.application.outputs.progress import PicksMade
from museflow.application.outputs.progress import PlaylistCreated
from museflow.application.outputs.progress import StepStarted
from museflow.application.outputs.progress import StrategyChosen
from museflow.application.ports.advisors.agent import AdvisorPort
from museflow.application.ports.progress import ProgressPort
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.discovery import DiscoveryService
from museflow.application.services.llm_usage import LLMUsageService
from museflow.application.utils.discovery import select_tracks
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import ProgressStep
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TasteProfileStatus
from museflow.domain.enums import TrackOrderBy
from museflow.domain.exceptions import DiscoveryTrackNoNewError
from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import TasteProfileStatusNotReadyError
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class CreateDiscoveryPlaylistResult:
    playlist: Playlist | None
    strategy: DiscoveryArtistStrategy
    tracks: list[Track]


class CreateDiscoveryPlaylistUseCase:
    """Use case for discovering new tracks guided by the user's AI taste profile."""

    def __init__(
        self,
        uow: UnitOfWorkPort,
        provider_library: ProviderLibraryPort,
        advisor: AdvisorPort,
        progress: ProgressPort,
    ) -> None:
        self._uow = uow
        self._advisor = advisor
        self._progress = progress
        # Application services built from the ports above, not ports: never injected
        self._discovery = DiscoveryService(uow=uow, provider_library=provider_library)
        self._llm_usage = LLMUsageService(uow=uow)

    async def create_playlist(
        self,
        user: User,
        config: CreateDiscoveryPlaylistConfigInput,
    ) -> CreateDiscoveryPlaylistResult:
        """Creates a playlist of suggested tracks guided by the user's taste profile.

        Each attempt asks the advisor for artists, fetches their catalogue tracks the user does not know, then
        asks the advisor to pick among them, so that no title can be invented. Iterates up to `max_attempts` times,
        each time excluding the artists already asked, and stops once `playlist_limit` tracks are kept after the
        per-artist cap, or once no other artist is wanted: an attempt suggests none, or only artists whose own tracks
        the request asks for. Those are searched deeper and not capped.

        Args:
            user: The user for whom to create the playlist.
            config: The configuration for the discovery process.

        Returns:
            A CreateDiscoveryPlaylistResult with the playlist (or None if dry-run), the last strategy, and the final list of
            tracks. Each step is published to the progress port as it runs.

        Raises:
            TasteProfileNotFoundError: If no matching taste profile is found.
            DiscoveryTrackNoNewError: If no new tracks are found after all attempts.
        """
        # Load everything the attempts need once, before the loop
        async with self._uow as uow:
            if config.profile_name is not None:
                profile = await uow.taste_profiles.get(user_id=user.id, name=config.profile_name)
            else:
                profile = await uow.taste_profiles.get_latest(user_id=user.id)

            if profile is None:
                raise TasteProfileNotFoundError()
            elif profile.status == TasteProfileStatus.BUILDING:
                raise TasteProfileStatusNotReadyError()

            blacklist = await uow.blacklist.get(user.id)
            liked_tracks = await uow.tracks.get_list(
                user_id=user.id,
                min_score=config.liked_tracks_score_threshold,
                limit=config.liked_tracks_limit,
            )
            disliked_tracks = await uow.tracks.get_list(
                user_id=user.id,
                max_score=config.disliked_tracks_score_threshold,
                exclude_skipped=True,
                order=[(TrackOrderBy.SCORE, SortOrder.ASC)],
                limit=config.disliked_tracks_limit,
            )

            # Told from the first attempt on, so that it suggests fewer known tracks (#154). It mirrors the
            # known-tracks filter, which drops any track of the library: if that filter changes, this count must
            # follow. The most played tracks were measured too: no gain, as 100 tracks barely cover a library of
            # thousands.
            covered_artists: dict[str, int] = {}
            if config.covered_artists_limit > 0:
                covered_artists = await uow.tracks.get_covered_artists(
                    user_id=user.id, limit=config.covered_artists_limit
                )

        # What the advisor spent is saved whatever the outcome: a failed discovery was billed too.
        playlist_id: uuid.UUID | None = None
        try:
            result = await self._discover(
                user, config, profile, blacklist, liked_tracks, disliked_tracks, covered_artists
            )
            playlist_id = result.playlist.id if result.playlist else None
        finally:
            await self._llm_usage.save(
                user_id=user.id,
                run_id=uuid.uuid4(),
                operation=LLMOperation.DISCOVER,
                usages=self._advisor.pop_usages(),
                profile_name=profile.name,
                playlist_id=playlist_id,
            )

        return result

    async def _discover(
        self,
        user: User,
        config: CreateDiscoveryPlaylistConfigInput,
        profile: TasteProfile,
        blacklist: UserBlacklist,
        liked_tracks: list[Track],
        disliked_tracks: list[Track],
        covered_artists: dict[str, int],
    ) -> CreateDiscoveryPlaylistResult:
        tracks_picked: list[TrackPicked] = []
        # What the playlist would hold now: the loop stops on it, so an attempt cut by the per-artist cap needs another.
        tracks: list[Track] = []
        strategy: DiscoveryArtistStrategy | None = None
        # The artists asked in earlier attempts, not to be suggested again.
        artists_asked: list[str] = []
        # The artists whose own tracks the request asks for, kept over the attempts: their tracks stay uncapped.
        artists_requested: set[str] = set()
        attempts_run = 0  # the attempts that went through their picks step, for the log

        for attempt in range(1, config.max_attempts + 1):
            await self._progress.publish(
                StepStarted(step=ProgressStep.DISCOVERY_ARTISTS, attempt=attempt, max_attempts=config.max_attempts)
            )
            strategy_now = await self._advisor.get_discovery_artists(
                profile=profile,
                artists_limit=config.advisor_limit,
                prompt=config.prompt,
                focus=config.focus,
                excluded_artists=list(artists_asked) or None,
                blacklisted_artists=blacklist.artist_names or None,
                blacklisted_tracks=blacklist.track_display_strings or None,
                liked_tracks=liked_tracks,
                disliked_tracks=disliked_tracks,
                covered_artists=covered_artists or None,
            )
            # No artist left: a request naming only artists already got them, another attempt would be paid for
            # nothing. The previous strategy is kept, as it chose the tracks.
            if not strategy_now.artists and strategy is not None:
                logger.debug(f"Attempt {attempt}/{config.max_attempts}: no artist left to suggest, stopping")
                break
            strategy = strategy_now

            artists_asked.extend(artist.name for artist in strategy.artists)
            artists_requested.update(artist.name for artist in strategy.artists if artist.requested)
            logger.debug(
                f"Discovery strategy: '{strategy.strategy_label}' ({len(strategy.artists)} artists)",
                extra={"strategy_label": strategy.strategy_label, "artists": len(strategy.artists)},
            )
            # After its log line, which shows above the display's line of the step
            await self._progress.publish(StrategyChosen(attempt=attempt, strategy=strategy))

            await self._progress.publish(StepStarted(step=ProgressStep.DISCOVERY_SEARCH, attempt=attempt))
            searches = await self._discovery.get_unknown_artist_tracks(
                user=user,
                artists=[artist.name for artist in strategy.artists],
                # Their own tracks are what the request asks for: the catalogue search reaches past the best-known.
                artists_deep={artist.name for artist in strategy.artists if artist.requested},
                blacklist=blacklist,
                fingerprints_kept={tp.track.fingerprint for tp in tracks_picked},
                artist_tracks_pages=config.artist_tracks_pages,
                catalogue_tracks_pages=config.requested_artist_tracks_pages,
                concurrency=config.artist_tracks_concurrency,
            )
            await self._progress.publish(CandidatesFound(attempt=attempt, searches=searches))
            candidates = {search.artist: search.tracks for search in searches if search.tracks}

            tracks_picked_now: list[TrackPicked] = []
            if candidates:
                await self._progress.publish(StepStarted(step=ProgressStep.DISCOVERY_PICKS, attempt=attempt))
                tracks_picked_now = await self._advisor.pick_discovery_tracks(
                    strategy=strategy,
                    candidates=candidates,
                    tracks_limit=config.advisor_limit,
                    max_tracks_per_artist=config.max_tracks_per_artist,
                    prompt=config.prompt,
                    focus=config.focus,
                )

            attempts_run = attempt
            tracks_picked.extend(tracks_picked_now)
            # The artists the request asks for are the playlist itself: no cap.
            tracks = select_tracks(
                tracks_picked=tracks_picked,
                max_tracks_per_artist=config.max_tracks_per_artist,
                playlist_limit=config.playlist_limit,
                uncapped_artists=artists_requested,
            )

            if candidates:
                await self._progress.publish(
                    PicksMade(attempt=attempt, picks=tracks_picked_now, tracks=tracks, target=config.playlist_limit)
                )

            logger.debug(
                f"Attempt {attempt}/{config.max_attempts}: +{len(tracks_picked_now)} tracks "
                f"(total: {len(tracks_picked)}, {len(tracks)} kept)",
                extra={"attempt": attempt, "total": len(tracks_picked), "kept": len(tracks)},
            )

            if len(tracks) >= config.playlist_limit:
                break
            # Only artists the request asks for: it names no other, and theirs were searched as deep as configured.
            if all(artist.requested for artist in strategy.artists):
                logger.debug(f"Attempt {attempt}/{config.max_attempts}: only requested artists, stopping")
                break

        # strategy can only be None if no attempt ran, which CreateDiscoveryPlaylistConfigInput forbids (max_attempts >= 1)
        if strategy is None or not tracks:
            raise DiscoveryTrackNoNewError()

        # The caller tells the user from the result
        if len(tracks) < config.playlist_limit:
            logger.info(
                f"playlist_limit not reached ({len(tracks)}/{config.playlist_limit}) after {attempts_run} attempt(s)",
                extra={"found": len(tracks), "target": config.playlist_limit, "attempts": attempts_run},
            )

        if config.dry_run:
            logger.debug("Dry-run mode: skipping playlist creation.")
            return CreateDiscoveryPlaylistResult(playlist=None, strategy=strategy, tracks=tracks)

        name = config.title or (
            f"[MF] - {strategy.suggested_playlist_name} - {datetime.now(UTC).isoformat(timespec='seconds')}"
        )
        await self._progress.publish(StepStarted(step=ProgressStep.PLAYLIST_CREATE))
        playlist = await self._discovery.create_playlist(
            name=name,
            type=PlaylistType.DISCOVERY,
            tracks=tracks,
            profile_id=profile.id,
            reasoning=strategy.reasoning,
            prompt=config.prompt,
            focus=config.focus,
        )
        await self._progress.publish(PlaylistCreated(playlist=playlist))
        return CreateDiscoveryPlaylistResult(playlist=playlist, strategy=strategy, tracks=playlist.tracks)
