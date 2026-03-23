from typing import Any
from typing import Self

import httpx

from wiremock.client import Mapping
from wiremock.client import MappingRequest
from wiremock.client import MappingResponse
from wiremock.client import Mappings
from wiremock.constants import Config


class WireMockContext:
    def __init__(self, base_url: str) -> None:
        self.admin_url = f"{base_url.rstrip('/')}/__admin"

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        # Reset all mappings and scenario states to file-based defaults.
        # Safe because @pytest.mark.wiremock (via --dist=loadgroup) ensures all tests
        # that share a WireMock server run on the same xdist worker sequentially —
        # no concurrent worker can have stubs deleted mid-test by this reset.
        httpx.post(f"{self.admin_url}/mappings/reset")

    def create_mapping(
        self,
        method: str,
        url_path: str,
        status: int,
        query_params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        priority: int = 1,
        scenario_name: str | None = None,
        required_state: str | None = None,
        new_state: str | None = None,
    ) -> None:
        mapping = Mapping(
            priority=priority,
            scenario_name=scenario_name,
            required_scenario_state=required_state,
            new_scenario_state=new_state,
            request=MappingRequest(
                method=method,
                url_path=url_path,
                query_parameters={k: {"equalTo": str(v)} for k, v in query_params.items()} if query_params else None,
            ),
            response=MappingResponse(
                status=status,
                json_body=json_body,
                headers={"Content-Type": "application/json"},
            ),
        )

        # We need to temporarily configure the final base_url Wiremock container
        original_base_url = Config.base_url
        try:
            Config.base_url = self.admin_url
            Mappings.create_mapping(mapping)
        finally:
            # Restore the global config to avoid side effects with other WireMockContext
            Config.base_url = original_base_url
