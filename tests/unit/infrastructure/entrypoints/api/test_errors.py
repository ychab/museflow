import logging

from fastapi import FastAPI
from fastapi import status
from fastapi.testclient import TestClient

import pytest

from museflow.infrastructure.entrypoints.api.errors import Problem
from museflow.infrastructure.entrypoints.api.errors import ProblemDetailsHandler


class _ParentError(Exception): ...


class _ChildError(_ParentError): ...


class TestProblemDetailsHandler:
    @pytest.fixture
    def client(self) -> TestClient:
        app = FastAPI()
        ProblemDetailsHandler({_ParentError: Problem(status=status.HTTP_409_CONFLICT, detail="Parent")}).register(app)

        @app.get("/child")
        async def child() -> None:
            raise _ChildError()

        @app.get("/unexpected")
        async def unexpected() -> None:
            raise RuntimeError("secret internals")

        return TestClient(app, raise_server_exceptions=False)

    def test__domain_error__subclass(self, client: TestClient) -> None:
        response = client.get("/child")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "Parent"

    def test__unexpected_error(self, client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR):
            response = client.get("/unexpected")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json() == {
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": 500,
            "detail": "An unexpected error occurred",
            "instance": "/unexpected",
        }
        assert "secret internals" not in response.text
        assert "Unexpected error: GET /unexpected" in caplog.text
