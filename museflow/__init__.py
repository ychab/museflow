from importlib.metadata import metadata
from importlib.metadata import version
from pathlib import Path
from typing import Final

PROJECT_DIR: Final[Path] = Path(__file__).parent
BASE_DIR: Final[Path] = PROJECT_DIR.parent

__project_name__ = metadata("museflow")["Name"]
__version__ = version("museflow")
