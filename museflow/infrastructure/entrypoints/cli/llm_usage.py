import logging
import uuid

from rich.console import Console
from rich.table import Table

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.llm_usage_record import record_llm_usage
from museflow.domain.enums import LLMOperation
from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter

logger = logging.getLogger(__name__)

console = Console()


def print_llm_usage(meter: LLMUsageMeter) -> None:
    """Prints what the command spent on LLM calls, per step and model: nothing when no call was made."""
    usages = meter.usages
    if not usages:
        return

    table = Table(title="LLM usage", show_footer=True)
    table.add_column("Step", footer="Total")
    table.add_column("Model")
    table.add_column("Calls", justify="right", footer=str(sum(usage.calls for usage in usages)))
    table.add_column("Prompt", justify="right", footer=f"{sum(usage.prompt_tokens for usage in usages):,}")
    table.add_column("Completion", justify="right", footer=f"{sum(usage.completion_tokens for usage in usages):,}")
    table.add_column("Reasoning", justify="right", footer=f"{sum(usage.reasoning_tokens for usage in usages):,}")
    table.add_column("Cost", justify="right", footer=f"${meter.total_cost:.4f}")
    for usage in usages:
        table.add_row(
            usage.step,
            usage.model,
            str(usage.calls),
            f"{usage.prompt_tokens:,}",
            f"{usage.completion_tokens:,}",
            f"{usage.reasoning_tokens:,}",
            f"${usage.cost:.4f}",
        )
    console.print(table)


async def save_llm_usage(
    user_id: uuid.UUID,
    operation: LLMOperation,
    meter: LLMUsageMeter | None,
    uow: UnitOfWorkPort,
    profile_name: str | None = None,
    playlist_id: uuid.UUID | None = None,
) -> None:
    """Saves what the command spent; a failure is only logged, so it never hides the command's own outcome."""
    if meter is None:
        return

    try:
        await record_llm_usage(
            user_id=user_id,
            operation=operation,
            usages=meter.usages,
            uow=uow,
            profile_name=profile_name,
            playlist_id=playlist_id,
        )
    except Exception:
        logger.exception("Failed to save the LLM usage", extra={"user_id": str(user_id), "operation": operation.value})
