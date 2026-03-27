import logging

from pydantic import HttpUrl
from pydantic import ValidationError

from museflow.application.ports.advisors.client import AdvisorClientPort
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.infrastructure.adapters.advisors.lastfm.mappers import to_track_suggested
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmSimilarTracksResponse
from museflow.infrastructure.adapters.http import HttpClientMixin

logger = logging.getLogger(__name__)


class LastFmClientAdapter(HttpClientMixin, AdvisorClientPort):
    """Adapter for the Last.fm API.

    This class implements the `AdvisorClientPort` and provides methods to interact
    with the Last.fm API to get similar tracks. It includes retry logic for
    transient network errors and specific HTTP status codes.
    """

    def __init__(
        self,
        client_api_key: str,
        client_secret: str,
        base_url: HttpUrl | None = None,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
        super().__init__(
            base_url=base_url or HttpUrl("http://ws.audioscrobbler.com/2.0/"),
            verify_ssl=verify_ssl,
            timeout=timeout,
        )

        self.client_api_key = client_api_key
        self.client_secret = client_secret

    @property
    def display_name(self) -> str:
        return "Last.fm"

    async def get_similar_tracks(self, artist_name: str, track_name: str, limit: int = 5) -> list[TrackSuggested]:
        tracks_suggested: list[TrackSuggested] = []

        response_data = await self.make_api_call(
            method="GET",
            endpoint="",
            params={
                "method": "track.getSimilar",
                "api_key": self.client_api_key,
                "format": "json",
                "artist": artist_name,
                "track": track_name,
                "limit": limit,
                "autocorrect": 1,
            },
        )

        try:
            page = LastFmSimilarTracksResponse.model_validate(response_data)
        except ValidationError as e:
            raise SimilarTrackResponseException(
                f"Invalid page for artist: {artist_name} and track: {track_name}",
            ) from e

        if page.error or page.message:
            logger.debug(
                f"Error occurred while fetching similar tracks for artist:'{artist_name}' and track:'{track_name}' "
                f"with error: {page.error or 0} and message: {page.message or ''}"
            )

        if page.similartracks:
            tracks_suggested = [to_track_suggested(track) for track in page.similartracks.track]

        return tracks_suggested
