import socket
from datetime import timedelta
from typing import Any
from typing import Final

from sqlalchemy.exc import InterfaceError
from sqlalchemy.exc import OperationalError

from celery import Celery
from celery import Task
from celery.signals import setup_logging
from celery.signals import worker_init
from celery.signals import worker_process_init
from celery.signals import worker_process_shutdown
from kombu import Exchange
from kombu import Queue

from museflow.infrastructure.config.loggers.setup import configure_loggers
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.config.settings.broker import broker_settings
from museflow.infrastructure.entrypoints.worker import dependencies

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


class MuseflowTask(Task):  # type: ignore[type-arg]
    """The retry policy of every task: transient errors only, with an exponential backoff and some jitter."""

    autoretry_for = TRANSIENT_ERRORS
    max_retries = app_settings.WORKER_TASK_MAX_RETRIES
    retry_backoff = True
    retry_backoff_max = app_settings.WORKER_TASK_RETRY_BACKOFF_MAX_SECONDS
    # Each wait drawn at random below its backoff: tasks that failed together (the database restarting) don't all retry
    # at the same second and bring it down again
    retry_jitter = True
    # Before the retry of a task whose process was lost (killed, out of memory)
    default_retry_delay = 10


celery_app = Celery(
    "museflow",
    broker=broker_settings.URL.get_secret_value(),  # type: ignore[union-attr]
    task_cls=MuseflowTask,
)
celery_app.conf.update(
    # A worker consumes both unless told one (`--queues`). A task goes to the batch queue, unless its name (`<theme>.`
    # first) routes it to the interactive one.
    task_queues=(BATCH_QUEUE, INTERACTIVE_QUEUE),
    task_routes={"playlist.*": {"queue": INTERACTIVE_QUEUE.name}},
    task_default_queue=BATCH_QUEUE.name,
    task_default_exchange=TASK_EXCHANGE.name,
    task_default_routing_key=BATCH_QUEUE.routing_key,
    # At least once: a message is acknowledged once its task ends, so that a worker dying mid-task leaves it to another
    # one. Every task is idempotent.
    task_acks_late=True,
    # A task that failed is rejected instead, without a requeue: RabbitMQ moves it to the dead-letter queue.
    task_acks_on_failure=False,
    # A process lost mid-task (the worker itself stays up): retried like a transient error, up to the same limit, then
    # dead-lettered. A requeue instead would loop forever on a task that kills its process every time.
    task_retry_on_worker_lost=True,
    # One message at a time per process: a long task never holds others back in its prefetch.
    worker_prefetch_multiplier=1,
    worker_concurrency=app_settings.WORKER_CONCURRENCY,
    # No result backend: the job state lives in the database.
    task_ignore_result=True,
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
)


@setup_logging.connect
def configure_worker_loggers(**kwargs: Any) -> None:
    """Our loggers instead of Celery's: connecting to this signal stops Celery from configuring logging."""
    configure_loggers(
        level=app_settings.LOG_LEVEL_WORKER,
        third_party_level=app_settings.LOG_LEVEL_THIRD_PARTY,
        handlers=app_settings.LOG_HANDLERS_WORKER,
    )


@worker_init.connect
def declare_dead_letter_queue(**kwargs: Any) -> None:
    """Declares the dead-letter queue, which no worker consumes, so that Celery would never declare it.

    Its exchange holds no message: without the queue bound to it, a message dead-lettered would be dropped.
    """
    with celery_app.connection_for_write() as connection:
        DEAD_LETTER_QUEUE(connection.default_channel).declare()


@worker_process_init.connect
def open_worker_process(**kwargs: Any) -> None:
    # In the child, after the fork: an engine, and the sockets of its pool, must never cross a fork.
    dependencies.open_process()


@worker_process_shutdown.connect
def close_worker_process(**kwargs: Any) -> None:
    dependencies.close_process()
