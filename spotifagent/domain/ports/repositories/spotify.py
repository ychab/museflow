import uuid
from abc import ABC
from abc import abstractmethod

from spotifagent.domain.entities.spotify import SpotifyAccount
from spotifagent.domain.entities.spotify import SpotifyAccountCreate
from spotifagent.domain.entities.spotify import SpotifyAccountUpdate


class SpotifyAccountRepositoryPort(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: uuid.UUID) -> SpotifyAccount | None: ...

    @abstractmethod
    async def create(
        self,
        user_id: uuid.UUID,
        spotify_account_data: SpotifyAccountCreate,
    ) -> SpotifyAccount | None: ...

    @abstractmethod
    async def update(self, user_id: uuid.UUID, spotify_account_data: SpotifyAccountUpdate) -> SpotifyAccount: ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID) -> None: ...
