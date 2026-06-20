class SpotifyTokenExpiredError(Exception): ...


class SpotifyRefreshTokenInvalidError(Exception): ...


class SpotifyApiError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
