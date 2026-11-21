import logging
from dataclasses import dataclass
from dataclasses import field
from http import HTTPStatus
from typing import Final

from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserAlreadyExistsError
from museflow.domain.exceptions import UserEmailAlreadyExistsError
from museflow.domain.exceptions import UserInactiveError
from museflow.domain.exceptions import UserInvalidCredentialsError
from museflow.infrastructure.entrypoints.api.schemas import ProblemDetails

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Problem:
    """How the API answers a domain exception: the status, and a fixed detail that never echoes the exception."""

    status: int
    detail: str
    headers: dict[str, str] = field(default_factory=dict)


class ProblemDetailsHandler:
    """Answers every error that leaves a route with an RFC 9457 problem details body.

    The domain exceptions get the problem their table gives; HTTP errors (the dependencies' 401, Starlette's 404),
    validation errors and unexpected errors take the same shape.
    """

    _MEDIA_TYPE: Final[str] = "application/problem+json"

    def __init__(self, problems: dict[type[Exception], Problem]) -> None:
        self._problems = problems

    def register(self, app: FastAPI) -> None:
        for exc_class in self._problems:
            app.add_exception_handler(exc_class, self.handle_domain_error)

        app.add_exception_handler(StarletteHTTPException, self.handle_http_error)
        app.add_exception_handler(RequestValidationError, self.handle_validation_error)
        app.add_exception_handler(Exception, self.handle_unexpected_error)

    async def handle_domain_error(self, request: Request, exc: Exception) -> JSONResponse:
        # A subclass gets the problem of its closest mapped parent, as Starlette picked this handler
        problem = next(self._problems[cls] for cls in type(exc).__mro__ if cls in self._problems)
        return self._respond(request, status_code=problem.status, detail=problem.detail, headers=problem.headers)

    async def handle_http_error(self, request: Request, exc: Exception) -> JSONResponse:
        # Raised by the dependencies (authentication, redirect URI) and by Starlette (404, 405)
        http_exc: StarletteHTTPException = exc  # type: ignore[assignment]
        return self._respond(
            request,
            status_code=http_exc.status_code,
            detail=str(http_exc.detail),
            headers=dict(http_exc.headers or {}),
        )

    async def handle_validation_error(self, request: Request, exc: Exception) -> JSONResponse:
        validation_exc: RequestValidationError = exc  # type: ignore[assignment]
        return self._respond(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The request is invalid",
            errors=jsonable_encoder(validation_exc.errors()),
        )

    async def handle_unexpected_error(self, request: Request, exc: Exception) -> JSONResponse:
        # The traceback stays in the logs: the client learns nothing of the internals
        logger.error(f"Unexpected error: {request.method} {request.url.path}", exc_info=exc)
        return self._respond(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )

    def _respond(
        self,
        request: Request,
        status_code: int,
        detail: str,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, object]] | None = None,
    ) -> JSONResponse:
        problem = ProblemDetails(
            title=HTTPStatus(status_code).phrase,
            status=status_code,
            detail=detail,
            instance=request.url.path,
            errors=errors,
        )
        return JSONResponse(
            content=problem.model_dump(exclude_none=True),
            status_code=status_code,
            headers=headers,
            media_type=self._MEDIA_TYPE,
        )


# The domain exceptions the routes let through; a route's own exceptions are added with the route
PROBLEMS: Final[dict[type[Exception], Problem]] = {
    # Accepted risk (#102): this answer reveals that the email has an account. A neutral one needs a full user workflow
    # with email verification, planned in #289 before the app is open to strangers.
    UserAlreadyExistsError: Problem(status=status.HTTP_409_CONFLICT, detail="Email already registered"),
    UserEmailAlreadyExistsError: Problem(status=status.HTTP_409_CONFLICT, detail="Email already registered"),
    UserInvalidCredentialsError: Problem(
        status=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    ),
    UserInactiveError: Problem(status=status.HTTP_403_FORBIDDEN, detail="User account is inactive"),
    ProviderOAuthStateInvalidError: Problem(status=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state"),
    # The adapter logs why the provider refused the code
    ProviderExchangeCodeError: Problem(status=status.HTTP_400_BAD_REQUEST, detail="Failed to exchange code"),
}
