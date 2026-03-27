from collections.abc import Iterable
from typing import Any
from unittest import mock

import httpx
from httpx import codes

from pydantic import HttpUrl

import pytest
from pytest_httpx import HTTPXMock
from tenacity import stop_after_attempt

from museflow.infrastructure.adapters.advisors.http import HttpAdvisorMixin


class DummyAdvisorAdapter(HttpAdvisorMixin): ...


class TestHttpAdvisorMixin:
    @pytest.fixture
    async def adapter(self) -> DummyAdvisorAdapter:
        return DummyAdvisorAdapter(base_url=HttpUrl("https://api.example.com/v1"))

    @pytest.fixture
    def mock_tenacity(self) -> Iterable[None]:
        retry_controller = HttpAdvisorMixin.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep
        original_stop = retry_controller.stop

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        retry_controller.stop = stop_after_attempt(5)
        yield
        retry_controller.sleep = original_sleep
        retry_controller.stop = original_stop

    @pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete", "head"])
    async def test__nominal(self, adapter: DummyAdvisorAdapter, httpx_mock: HTTPXMock, method: str) -> None:
        response_json: dict[str, Any] = {"ok": True}
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method=method.upper(),
            json=response_json,
        )

        result = await adapter.make_api_call(method=method, endpoint="/test")

        assert result == response_json

    async def test__no_content(self, adapter: DummyAdvisorAdapter, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=codes.NO_CONTENT)

        result = await adapter.make_api_call(method="GET", endpoint="/test")

        assert result == {}

    @pytest.mark.parametrize("status_code", [codes.UNAUTHORIZED, codes.FORBIDDEN])
    async def test__retry__not_on_4xx(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
        status_code: int,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            status_code=status_code,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.make_api_call(method="GET", endpoint="/test")

        assert exc_info.value.response.status_code == status_code
        assert len(httpx_mock.get_requests()) == 1

    async def test__retry__not_on_generic_error(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_exception(RuntimeError("Unexpected crash"))

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await adapter.make_api_call(method="GET", endpoint="/test")

        assert len(httpx_mock.get_requests()) == 1

    async def test__retry__on_5xx(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            status_code=codes.INTERNAL_SERVER_ERROR,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            status_code=codes.SERVICE_UNAVAILABLE,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            json={"ok": True},
        )

        result = await adapter.make_api_call(method="GET", endpoint="/test")

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 3

    async def test__retry__network_error(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("Network down"))
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            json={"ok": True},
        )
        result = await adapter.make_api_call(method="GET", endpoint="/test")

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__retry__max_attempts_exceeded(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        for _ in range(5):
            httpx_mock.add_response(
                url="https://api.example.com/v1/test",
                method="GET",
                status_code=codes.INTERNAL_SERVER_ERROR,
            )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.make_api_call(method="GET", endpoint="/test")

        assert exc_info.value.response.status_code == codes.INTERNAL_SERVER_ERROR
        assert len(httpx_mock.get_requests()) == 5

    async def test__retry__rate_limit(
        self,
        adapter: DummyAdvisorAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            status_code=codes.TOO_MANY_REQUESTS,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/test",
            method="GET",
            json={"ok": True},
        )

        result = await adapter.make_api_call(method="GET", endpoint="/test")

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2
