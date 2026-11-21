from typing import Final

# Part of the API contract, published in the OpenAPI schema (the paths, the page limits): clients rely on it, so it is
# a constant, never a setting that could vary between deployments.
API_V1_PREFIX: Final[str] = "/api/v1"

PAGE_LIMIT_DEFAULT: Final[int] = 20
PAGE_LIMIT_MAX: Final[int] = 100
