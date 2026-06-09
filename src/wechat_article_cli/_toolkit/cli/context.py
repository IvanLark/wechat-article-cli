"""CLI 运行时上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

OutputMode = Literal["human", "json", "yaml", "ndjson"]


@dataclass(slots=True)
class CommandContext:
    capability_name: str
    command_path: str
    output_mode: OutputMode
    debug: bool = False
    verbose: bool = False
    capability_home: Path | None = None
    config_path: Path | None = None
    is_tty: bool = True

