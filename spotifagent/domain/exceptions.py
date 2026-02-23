class UserNotFound(Exception):
    pass


class UserAlreadyExistsException(Exception):
    pass


class UserEmailAlreadyExistsException(Exception):
    pass


class UserInactive(Exception):
    pass


class UserInvalidCredentials(Exception):
    pass


class ProviderAuthTokenNotFoundError(Exception):
    pass


class ProviderExchangeCodeError(Exception):
    pass


class SpotifyAccountNotFoundError(Exception):
    """Raised when an operation requires a linked Spotify account but none exists."""

    pass


class SpotifyPageValidationError(Exception):
    pass
