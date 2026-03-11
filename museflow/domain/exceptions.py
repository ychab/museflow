from typing import Literal

ProviderPageErrorCodes = Literal["unsupported_local_files"]


# --- User exceptions ---


class UserNotFound(Exception): ...


class UserAlreadyExistsException(Exception): ...


class UserEmailAlreadyExistsException(Exception): ...


class UserInactive(Exception): ...


class UserInvalidCredentials(Exception): ...


# --- Provider exceptions ---


class ProviderAuthTokenNotFoundError(Exception): ...


class ProviderExchangeCodeError(Exception): ...


class ProviderPageValidationError(Exception):
    def __init__(self, msg: str, code: ProviderPageErrorCodes | None = None) -> None:
        self.code = code
        super().__init__(msg)


# --- Similarity track exceptions ---


class SimilarTrackResponseException(Exception): ...


# --- Discovery track exceptions ---


class DiscoveryTrackException(Exception): ...


class DiscoveryTrackNoSeedFound(DiscoveryTrackException): ...


class DiscoveryTrackNoSimilarFound(DiscoveryTrackException): ...


class DiscoveryTrackNoReconciledFound(DiscoveryTrackException): ...


class DiscoveryTrackNoNew(DiscoveryTrackException): ...
