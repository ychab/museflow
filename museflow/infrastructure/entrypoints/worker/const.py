import socket
from datetime import timedelta
from typing import Final

from sqlalchemy.exc import InterfaceError
from sqlalchemy.exc import OperationalError

from kombu import Exchange
from kombu import Queue

from museflow.domain.enums import JobKind

# How long RabbitMQ lets a consumer hold a message unacknowledged before it closes its channel (30 minutes by default).
# A task acknowledges its message once it ends (acks late): the timeout of a queue must outlast its longest task, and
# the shorter it is, the sooner a consumer that hangs for good is caught.
# A first enrichment, the longest job, took 8 minutes for 10,000 tracks (51 LLM batches of 200): 2 hours leave room for
# a library several times larger and for the LLM retries.
BATCH_CONSUMER_TIMEOUT: Final[timedelta] = timedelta(hours=2)
# A playlist takes a minute or two (estimated, until #267 measures it): several times that, LLM retries included.
INTERACTIVE_CONSUMER_TIMEOUT: Final[timedelta] = timedelta(minutes=15)

# Where RabbitMQ moves a message rejected for good: a task that failed after its retries, or on an error not worth one.
# One for both task queues: a message keeps its queue in its `x-first-death-queue` header, and its task in `task`.
DEAD_LETTER_QUEUE: Final[Queue] = Queue(
    "museflow.dead_letter",
    Exchange("museflow.dead_letter", type="direct"),
    routing_key="museflow.dead_letter",
)

# The task queues, split by who waits for the result, each consumed by workers of its own: the slots of a worker are
# shared by all its queues, and a priority never stops a task already running, so only workers apart keep a playlist
# from waiting behind an enrichment. A queue is never renamed, nor its arguments changed: RabbitMQ refuses to declare
# it again with other ones (PRECONDITION_FAILED); it takes a new queue, drained, then the old one deleted.
TASK_EXCHANGE: Final[Exchange] = Exchange("museflow", type="direct")
# Background work no one watches, long and paid: history import, enrichment, taste profile build
BATCH_QUEUE: Final[Queue] = Queue(
    "museflow.batch",
    TASK_EXCHANGE,
    routing_key="museflow.batch",
    queue_arguments={
        "x-dead-letter-exchange": DEAD_LETTER_QUEUE.exchange.name,
        "x-dead-letter-routing-key": DEAD_LETTER_QUEUE.routing_key,
        "x-consumer-timeout": int(BATCH_CONSUMER_TIMEOUT.total_seconds() * 1000),
    },
)
# What a user waits for, in front of the screen: the playlists
INTERACTIVE_QUEUE: Final[Queue] = Queue(
    "museflow.interactive",
    TASK_EXCHANGE,
    routing_key="museflow.interactive",
    queue_arguments={
        "x-dead-letter-exchange": DEAD_LETTER_QUEUE.exchange.name,
        "x-dead-letter-routing-key": DEAD_LETTER_QUEUE.routing_key,
        "x-consumer-timeout": int(INTERACTIVE_CONSUMER_TIMEOUT.total_seconds() * 1000),
    },
)

# The errors a new try may not meet: the database or the network briefly unreachable. Any other error (a domain
# error, a bug) would fail the same way again. The HTTP adapters already retry their own calls.
TRANSIENT_ERRORS: Final[tuple[type[Exception], ...]] = (
    ConnectionError,
    TimeoutError,
    socket.gaierror,
    OperationalError,
    InterfaceError,
)

# The task each kind of job runs: `<theme>.<verb>`, which routes it to its queue (`task_routes`)
JOB_TASK_NAMES: Final[dict[JobKind, str]] = {
    JobKind.TRACK_HISTORY_IMPORT: "track.history_import",
}
