from typing import Final

# Part of the API contract, published in the OpenAPI schema: constants, not settings, so that it never varies between
# deployments.
PAGE_LIMIT_DEFAULT: Final[int] = 20
PAGE_LIMIT_MAX: Final[int] = 100
