from typing import Any
from typing import Self

import httpx


class WireMockContext:
    def __init__(self, base_url: str) -> None:
        self.admin_url = f"{base_url.rstrip('/')}/__admin"
        self._mapping_ids: list[str] = []
        self._has_scenarios: bool = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        for mapping_id in self._mapping_ids:
            httpx.delete(f"{self.admin_url}/mappings/{mapping_id}")
        self._mapping_ids.clear()

        # Reset scenario states only when this context used scenarios, so the next
        # test that uses the same scenario name starts from the "Started" state.
        if self._has_scenarios:
            httpx.post(f"{self.admin_url}/scenarios/reset")
            self._has_scenarios = False

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
        body: dict[str, Any] = {
            "priority": priority,
            "request": {
                "method": method,
                "urlPath": url_path,
            },
            "response": {
                "status": status,
                "headers": {"Content-Type": "application/json"},
            },
        }
        if query_params:
            body["request"]["queryParameters"] = {k: {"equalTo": str(v)} for k, v in query_params.items()}
        if json_body is not None:
            body["response"]["jsonBody"] = json_body
        if scenario_name:
            body["scenarioName"] = scenario_name
            self._has_scenarios = True
        if required_state:
            body["requiredScenarioState"] = required_state
        if new_state:
            body["newScenarioState"] = new_state

        response = httpx.post(f"{self.admin_url}/mappings", json=body)
        response.raise_for_status()
        self._mapping_ids.append(response.json()["id"])
