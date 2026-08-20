from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class McpPreflightCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class McpSetupInformation:
    version: str
    executable_path: Path
    data_path: Path
    database_path: Path
    command: str
    command_prefix_arguments: tuple[str, ...]

