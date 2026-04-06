import json

from museflow.infrastructure.adapters.common.gemini.utils import parse_retry_delay


class TestParseRetryDelay:
    def test__valid(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "38s"},
                    ]
                }
            }
        ).encode()

        assert parse_retry_delay(body) == 38

    def test__decimal_seconds(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "38.9s"},
                    ]
                }
            }
        ).encode()

        assert parse_retry_delay(body) == 38

    def test__no_detail(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "details": [
                        {"@type": "type.googleapis.com/google.rpc.Help", "links": []},
                    ]
                }
            }
        ).encode()

        assert parse_retry_delay(body) is None

    def test__malformed_body(self) -> None:
        assert parse_retry_delay(b"not-json") is None

    def test__empty_details(self) -> None:
        body = json.dumps({"error": {"details": []}}).encode()

        assert parse_retry_delay(body) is None
