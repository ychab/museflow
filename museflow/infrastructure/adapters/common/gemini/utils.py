import json


def parse_retry_delay(content: bytes) -> int | None:
    """Extracts the retryDelay (in seconds) from a Gemini 429 response body.

    Gemini embeds the delay inside error.details[] under the RetryInfo entry,
    as a string like "38s". Returns None if the body is malformed or missing.
    """
    try:
        body = json.loads(content)
        for detail in body.get("error", {}).get("details", []):
            if detail.get("@type", "").endswith("RetryInfo") and "retryDelay" in detail:
                return int(float(detail["retryDelay"].rstrip("s")))
    except (ValueError, KeyError, AttributeError, TypeError):
        pass

    return None
