from collections.abc import Iterable
from typing import Any
from unittest import mock

import httpx
from httpx import codes

from pydantic import HttpUrl

import pytest
from pytest_httpx import HTTPXMock
from tenacity import stop_after_attempt

from museflow.domain.value_objects.auth import OAuthProviderTokenPayload
from museflow.infrastructure.adapters.providers.http import HttpProviderMixin

from tests.unit.factories.value_objects.auth import OAuthProviderTokenPayloadFactory


class DummyProviderAdapter(HttpProviderMixin): ...


class TestHttpProviderMixin:
    @pytest.fixture
    async def adapter(self) -> DummyProviderAdapter:
        return DummyProviderAdapter(
            base_url=HttpUrl("https://api.example.com/v1"),
            token_endpoint=HttpUrl("https://api.example.com/token"),
        )

    @pytest.fixture
    def token_payload(self) -> OAuthProviderTokenPayload:
        return OAuthProviderTokenPayloadFactory.build()

    @pytest.fixture
    def mock_tenacity(self) -> Iterable[None]:
        retry_controller = HttpProviderMixin.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep
        original_stop = retry_controller.stop

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        retry_controller.stop = stop_after_attempt(5)
        yield
        retry_controller.sleep = original_sleep
        retry_controller.stop = original_stop

    async def test__nominal(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
    ) -> None:
        response_json: dict[str, Any] = {"ok": True}
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            json=response_json,
        )

        result = await adapter.make_api_call(
            method="GET",
            endpoint="/tracks",
            token_payload=token_payload,
        )

        assert result == response_json

    async def test__no_content(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            status_code=codes.NO_CONTENT,
        )

        result = await adapter.make_api_call(
            method="GET",
            endpoint="/tracks",
            token_payload=token_payload,
        )

        assert result == {}

    async def test__retry__on_server_error(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            status_code=codes.INTERNAL_SERVER_ERROR,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            json={"ok": True},
        )

        result = await adapter.make_api_call(
            method="GET",
            endpoint="/tracks",
            token_payload=token_payload,
        )

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__retry__on_network_error(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("Network down"))
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            json={"ok": True},
        )

        result = await adapter.make_api_call(
            method="GET",
            endpoint="/tracks",
            token_payload=token_payload,
        )

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__retry__max_attempts_exceeded(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        for _ in range(5):
            httpx_mock.add_response(
                url="https://api.example.com/v1/tracks",
                method="GET",
                status_code=codes.INTERNAL_SERVER_ERROR,
            )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.make_api_call(
                method="GET",
                endpoint="/tracks",
                token_payload=token_payload,
            )

        assert exc_info.value.response.status_code == codes.INTERNAL_SERVER_ERROR
        assert len(httpx_mock.get_requests()) == 5

    @pytest.mark.parametrize("status_code", [codes.UNAUTHORIZED, codes.FORBIDDEN])
    async def test__retry__not_on_4xx(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
        status_code: int,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            status_code=status_code,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await adapter.make_api_call(method="GET", endpoint="/tracks", token_payload=token_payload)

        assert exc_info.value.response.status_code == status_code
        assert len(httpx_mock.get_requests()) == 1

    async def test__retry__not_on_generic_error(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_exception(RuntimeError("Unexpected crash"))

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await adapter.make_api_call(method="GET", endpoint="/tracks", token_payload=token_payload)

        assert len(httpx_mock.get_requests()) == 1

    async def test__retry__rate_limit(
        self,
        adapter: DummyProviderAdapter,
        token_payload: OAuthProviderTokenPayload,
        httpx_mock: HTTPXMock,
        mock_tenacity: None,
    ) -> None:
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            status_code=codes.TOO_MANY_REQUESTS,
        )
        httpx_mock.add_response(
            url="https://api.example.com/v1/tracks",
            method="GET",
            json={"ok": True},
        )

        result = await adapter.make_api_call(method="GET", endpoint="/tracks", token_payload=token_payload)

        assert result == {"ok": True}
        assert len(httpx_mock.get_requests()) == 2
