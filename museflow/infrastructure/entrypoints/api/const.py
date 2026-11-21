from typing import Final

# The API contract (its paths, the page limits published in the OpenAPI schema): constants, not settings, so that
# it never varies between deployments.
API_V1_PREFIX: Final[str] = "/api/v1"

PAGE_LIMIT_DEFAULT: Final[int] = 20
PAGE_LIMIT_MAX: Final[int] = 100
