import re
from collections.abc import Iterable
from typing import Any
from unittest import mock

import httpx
from httpx import codes

import pytest
from pytest_httpx import HTTPXMock

from museflow.domain.exceptions import SimilarTrackResponseException
from museflow.infrastructure.adapters.advisors.lastfm.client import LastFmClientAdapter


class TestLastFmClientAdapter:
    @pytest.fixture
    def mock_tenacity_sleep(self) -> Iterable[None]:
        retry_controller = LastFmClientAdapter.make_api_call.retry  # type: ignore[attr-defined]
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    async def test__get_similar_tracks__none(self, lastfm_client: LastFmClientAdapter, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            json={"similartracks": {"track": []}},
        )

        tracks_suggested = await lastfm_client.get_similar_tracks(
            artist_name="dummy-artist",
            track_name="dummy-track",
            limit=20,
        )

        assert len(tracks_suggested) == 0

    async def test__get_similar_tracks__response_exception(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            json={
                "similartracks": {
                    "track": [
                        {
                            "artist": {
                                "mbid": "5436ce22-af50-4714-addc-afd5d2efc77f",
                                "name": "Grupo Niche",
                            },
                            "match": 71.5,
                            "mbid": "2ced3803-b87a-319f-9926-0388b20608be",
                            "name": "Mi Pueblo",
                        },
                    ],
                },
            },
        )

        with pytest.raises(SimilarTrackResponseException):
            await lastfm_client.get_similar_tracks(
                artist_name="dummy-artist",
                track_name="dummy-track",
            )

    @pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete", "head"])
    async def test__make_api_call__nominal(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
        method: str,
    ) -> None:
        response_json: dict[str, Any] = {"succeed": True}

        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method=method.upper(),
            json=response_json,
        )

        response_data = await lastfm_client.make_api_call(method=method)

        assert response_data == response_json

    async def test__make_api_call__no_content(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(status_code=codes.NO_CONTENT)

        response_data = await lastfm_client.make_api_call(method="GET")

        assert response_data == {}

    @pytest.mark.parametrize("status_code", [codes.UNAUTHORIZED, codes.FORBIDDEN])
    async def test__make_user_api_call__retry__not_on_4xx(
        self,
        lastfm_client: LastFmClientAdapter,
        status_code: int,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=status_code,
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await lastfm_client.make_api_call(method="GET")

        assert exc_info.value.response.status_code == status_code
        assert len(httpx_mock.get_requests()) == 1

    async def test__make_api_call__retry__not_on_generic_error(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_exception(RuntimeError("Unexpected crash"))

        with pytest.raises(RuntimeError, match="Unexpected crash"):
            await lastfm_client.make_api_call(method="GET")

        assert len(httpx_mock.get_requests()) == 1

    async def test__make_api_call__retry__on_5xx(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.INTERNAL_SERVER_ERROR,  # 500
        )
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.SERVICE_UNAVAILABLE,  # 503
        )
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.OK,  # 200
            json={"success": True},
        )

        response = await lastfm_client.make_api_call(method="GET")

        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 3

    async def test__make_api_call__retry__network_error(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_exception(httpx.ConnectError("Network down"))
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.OK,
            json={"success": True},
        )

        response = await lastfm_client.make_api_call(method="GET")

        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2

    async def test__make_api_call__retry__max_attempts_exceeded(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        for _ in range(5):
            httpx_mock.add_response(
                url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
                method="GET",
                status_code=codes.INTERNAL_SERVER_ERROR,
            )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await lastfm_client.make_api_call(method="GET")

        assert exc_info.value.response.status_code == codes.INTERNAL_SERVER_ERROR
        assert len(httpx_mock.get_requests()) == 5

    async def test__make_api_call__retry__rate_limit(
        self,
        lastfm_client: LastFmClientAdapter,
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.TOO_MANY_REQUESTS,
        )
        httpx_mock.add_response(
            url=re.compile(f"^{re.escape(str(lastfm_client.base_url))}.*"),
            method="GET",
            status_code=codes.OK,
            json={"success": True},
        )

        response = await lastfm_client.make_api_call(method="GET")

        assert response == {"success": True}
        assert len(httpx_mock.get_requests()) == 2
