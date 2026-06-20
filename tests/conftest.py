import logging
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime

import pytest
from time_machine import TimeMachineFixture


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="run slow tests",
    )
    parser.addoption(
        "--spotify-refresh-token",
        action="store",
        default=None,
        help="A valid Spotify Refresh Token to run live API tests.",
    )
    parser.addoption(
        "--gemini-live",
        action="store_true",
        default=False,
        help="Run live Gemini API tests (requires GEMINI_API_KEY).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: mark test as slow (not executed by default)")
    config.addinivalue_line("markers", "spotify_live: mark test as requiring live Spotify API access")
    config.addinivalue_line("markers", "gemini_live: mark test as requiring live Gemini API access")
    config.addinivalue_line(
        "markers",
        "wiremock(*servers): test uses one or more WireMock servers ('spotify', 'gemini') — "
        "groups tests by server set so each group runs serially on a single xdist worker",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Create skip markers.
    skip_slow = pytest.mark.skip(reason="need --slow option to run")
    skip_spotify = pytest.mark.skip(reason="need --spotify-refresh-token option to run")

    wiremock_server_groups = get_wiremock_server_groups(items)

    # Automatically skip marked tests if the corresponding parse option is missing.
    # Group WireMock tests onto a single xdist worker so stub resets don't race.
    for item in items:
        if item.get_closest_marker("slow") and not config.getoption("--slow"):
            item.add_marker(skip_slow)

        if item.get_closest_marker("spotify_live") and not config.getoption("--spotify-refresh-token"):
            item.add_marker(skip_spotify)

        if item.get_closest_marker("gemini_live") and not config.getoption("--gemini-live"):
            item.add_marker(pytest.mark.skip(reason="need --gemini-live option to run"))

        if group_name := get_wiremock_group_name(item, wiremock_server_groups):
            item.add_marker(pytest.mark.xdist_group(group_name))


@pytest.fixture(scope="session", autouse=True)
def anyio_backend() -> str:
    """
    Configure anyio backend for all async tests.
    @see https://anyio.readthedocs.io/en/stable/testing.html#using-async-fixtures-with-higher-scopes
    """
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def configure_logging() -> Iterable[None]:
    """Configure logging for ALL tests before anything else"""
    from museflow.infrastructure.config.loggers import configure_loggers

    # Configure with test-friendly settings
    configure_loggers(level="DEBUG", handlers=["null"], propagate=True)

    yield

    logging.shutdown()


@pytest.fixture
def frozen_time(time_machine: TimeMachineFixture) -> datetime:
    fixed_dt = datetime(2026, 1, 1, tzinfo=UTC)
    time_machine.move_to(fixed_dt, tick=False)
    return fixed_dt


def get_wiremock_server_groups(items: list[pytest.Item]) -> dict[str, set[str]]:
    """Map each WireMock server name to the full set of servers it must share an xdist group with.

    Tests are marked `@pytest.mark.wiremock(*servers)`. Two servers must end up in the same
    xdist group if any single test uses both (e.g. `wiremock("gemini", "spotify")`) — and that
    requirement is transitive: if test A uses only "spotify" and test B uses "gemini" and
    "spotify", then A and B must share a group too, even though A never mentions "gemini".
    Without this, two tests could run concurrently on different xdist workers while hitting the
    same physical WireMock instance, racing on stub mappings (a one-off override stub created by
    one test can be matched by a request from another test before it's torn down).

    Computed via union-find: each test's marker args union their servers into one group.
    """
    parent: dict[str, str] = {}

    def find(server: str) -> str:
        parent.setdefault(server, server)
        while parent[server] != server:
            parent[server] = parent[parent[server]]
            server = parent[server]
        return server

    def union(server_a: str, server_b: str) -> None:
        root_a, root_b = find(server_a), find(server_b)
        if root_a != root_b:
            parent[root_a] = root_b

    for item in items:
        if marker := item.get_closest_marker("wiremock"):
            servers = sorted(set(marker.args))
            for server in servers[1:]:
                union(servers[0], server)

    components: dict[str, set[str]] = {}
    for server in parent:
        components.setdefault(find(server), set()).add(server)

    return {server: members for members in components.values() for server in members}


def get_wiremock_group_name(item: pytest.Item, wiremock_server_groups: dict[str, set[str]]) -> str | None:
    marker = item.get_closest_marker("wiremock")
    if not marker:
        return None
    return "wiremock-" + "-".join(sorted(wiremock_server_groups[next(iter(set(marker.args)))]))
