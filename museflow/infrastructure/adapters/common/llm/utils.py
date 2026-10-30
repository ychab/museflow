import httpx


def parse_retry_after(response: httpx.Response) -> int | None:
    """Extracts the delay (in seconds) of a `Retry-After` header, the form OpenRouter uses on 429 and 503 replies.

    The HTTP-date form is not handled. Returns None if the header is missing or not a number of seconds.
    """
    value = response.headers.get("Retry-After")
    if value is None:
        return None

    try:
        return max(0, int(float(value)))
    except ValueError:
        return None
