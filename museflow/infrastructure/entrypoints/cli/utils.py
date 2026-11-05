from contextlib import nullcontext

from rich import get_console
from rich.console import Console
from rich.status import Status
from rich.table import Table

from museflow.infrastructure.adapters.common.llm.usage import LLMUsageMeter

console = Console()


def working(message: str) -> Status | nullcontext[None]:
    live_console = get_console()
    return live_console.status(message) if live_console.is_terminal else nullcontext()


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
