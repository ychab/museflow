import logging
from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

from spotifagent.application.services.spotify import SpotifySessionFactory
from spotifagent.application.services.spotify import SpotifyUserSession
from spotifagent.application.services.spotify import TimeRange
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import SpotifyAccountNotFoundError
from spotifagent.domain.ports.repositories.music import ArtistRepositoryPort
from spotifagent.domain.ports.repositories.music import TrackRepositoryPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SyncReport:
    purge_artist: int = 0
    purge_track: int = 0

    artist_created: int = 0
    artist_updated: int = 0

    track_created: int = 0
    track_updated: int = 0

    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


async def spotify_sync(
    user: User,
    spotify_session_factory: SpotifySessionFactory,
    artist_repository: ArtistRepositoryPort,
    track_repository: TrackRepositoryPort,
    purge_artists: bool = False,
    purge_tracks: bool = False,
    sync_artists: bool = False,
    sync_tracks: bool = False,
    page_limit: int = 50,
    time_range: TimeRange = "long_term",
    batch_size: int = 300,
) -> SyncReport:
    """
    For a given user, synchronize its Spotify items, including artists
    and tracks, depending on the given flags.

    :param user: A user object
    :param spotify_session_factory: Spotify session factory
    :param artist_repository: Artists repository
    :param track_repository: Tracks repository
    :param purge_artists: Whether to purge artists
    :param purge_tracks: Whether to purge tracks
    :param sync_artists: Whether to sync artists (fetch and save)
    :param sync_tracks: Whether to sync tracks (fetch and save)
    :param page_limit: The number of items to fetch
    :param time_range: The time range to fetch
    :param batch_size: The number of items to bulk upsert in DB
    :return: SyncReport
    """
    report = SyncReport()

    # First of all, purge items if required.
    if purge_artists:
        report = await _purge_artists(user, artist_repository, report)
        if report.has_errors:
            return report

    if purge_tracks:
        report = await _purge_tracks(user, track_repository, report)
        if report.has_errors:
            return report

    # Then init a spotify user session.
    try:
        spotify_session = spotify_session_factory.create(user)
    except SpotifyAccountNotFoundError:
        logger.debug(f"Spotify account not found for user {user.email}")
        return replace(report, errors=["You must connect your Spotify account first."])

    # Then fetch artists and upsert them in DB.
    if sync_artists:
        report = await _sync_artists(
            spotify_session=spotify_session,
            artist_repository=artist_repository,
            page_limit=page_limit,
            time_range=time_range,
            batch_size=batch_size,
            report=report,
        )

    # Then fetch tracks and upsert them in DB.
    if sync_tracks:
        report = await _sync_tracks(
            spotify_session=spotify_session,
            track_repository=track_repository,
            page_limit=page_limit,
            time_range=time_range,
            batch_size=batch_size,
            report=report,
        )

    return report


async def _purge_artists(
    user: User,
    artist_repository: ArtistRepositoryPort,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About purging artists for user {user.email}...")

    try:
        count_artist = await artist_repository.purge(user_id=user.id)
    except Exception:
        logger.exception(f"An error occurred while purging artists for user {user.email}")
        report = replace(report, errors=["An error occurred while purging your artists."])
    else:
        report = replace(report, purge_artist=count_artist)
        logger.info(f"Successfully purged {count_artist} artists for user {user.email}")

    return report


async def _purge_tracks(
    user: User,
    track_repository: TrackRepositoryPort,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About purging tracks for user {user.email}...")

    try:
        count_track = await track_repository.purge(user_id=user.id)
    except Exception:
        logger.exception(f"An error occurred while purging tracks for user {user.email}")
        report = replace(report, errors=["An error occurred while purging your tracks."])
    else:
        report = replace(report, purge_track=count_track)
        logger.info(f"Successfully purged {count_track} tracks for user {user.email}")

    return report


async def _sync_artists(
    spotify_session: SpotifyUserSession,
    artist_repository: ArtistRepositoryPort,
    page_limit: int,
    time_range: TimeRange,
    batch_size: int,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About synchronizing artists for user {spotify_session.user.email}...")

    try:
        artists = await spotify_session.get_top_artists(limit=page_limit, time_range=time_range)
    except Exception:
        logger.exception(f"An error occurred while fetching artists for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while fetching Spotify artists."])
    else:
        logger.info(f"Fetched {len(artists)} artists for user {spotify_session.user.email}")

    try:
        artist_ids, created = await artist_repository.bulk_upsert(artists, batch_size=batch_size)
    except Exception:
        logger.exception(f"An error occurred while upserting artists for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while saving Spotify artists."])
    else:
        logger.info(f"Upserted {len(artist_ids)} artists for user {spotify_session.user.email}")

    return replace(report, artist_created=created, artist_updated=len(artist_ids) - created)


async def _sync_tracks(
    spotify_session: SpotifyUserSession,
    track_repository: TrackRepositoryPort,
    page_limit: int,
    time_range: TimeRange,
    batch_size: int,
    report: SyncReport,
) -> SyncReport:
    logger.info(f"About synchronizing tracks for user {spotify_session.user.email}...")

    try:
        tracks = await spotify_session.get_top_tracks(limit=page_limit, time_range=time_range)
    except Exception:
        logger.exception(f"An error occurred while fetching tracks for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while fetching Spotify tracks."])
    else:
        logger.info(f"Fetched {len(tracks)} tracks for user {spotify_session.user.email}")

    try:
        track_ids, created = await track_repository.bulk_upsert(tracks, batch_size=batch_size)
    except Exception:
        logger.exception(f"An error occurred while upserting tracks for user {spotify_session.user.email}")
        return replace(report, errors=["An error occurred while saving Spotify tracks."])
    else:
        logger.info(f"Upserted {len(track_ids)} tracks for user {spotify_session.user.email}")

    return replace(report, track_created=created, track_updated=len(track_ids) - created)
