from pathlib import Path
from typing import Any

import typer
import yaml


def read_yaml(path: Path) -> Any:
    """Loads a YAML file, exiting the command with an error message when it is missing or invalid."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        typer.secho(f"Error: File not found: {path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as e:
        typer.secho(f"Error: Invalid YAML file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    return data


def write_yaml(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
