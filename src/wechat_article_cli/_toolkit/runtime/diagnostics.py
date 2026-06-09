"""CLI diagnostics / logging。

当前仍然保留对 legacy capability 的兼容行为：
- INFO/SUCCESS 默认走 stdout
- WARNING/ERROR/DEBUG 走 stderr

后续 capability 逐步迁移后，业务结果输出应完全转移到 `toolkit.protocol.output`。
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from wechat_article_cli._toolkit.runtime.home import get_logs_dir

_initialized = False


def configure_diagnostics(
    *,
    capability_name: str,
    debug: bool = False,
    verbose: bool = False,
    log_file: bool | Path = False,
    info_to_stdout: bool = True,
) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    logger.remove()

    info_stream = sys.stdout if info_to_stdout else sys.stderr
    logger.add(
        info_stream,
        level="INFO",
        colorize=False,
        format="{message}",
        filter=lambda record: record["level"].name in {"INFO", "SUCCESS"},
    )

    logger.add(
        sys.stderr,
        level="WARNING",
        colorize=False,
        format="{message}",
    )

    if debug or verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            colorize=False,
            format="{time:HH:mm:ss} | {level:<7} | {name} - {message}",
            filter=lambda record: record["level"].name == "DEBUG",
        )

    if log_file:
        log_path = Path(log_file) if isinstance(log_file, Path) else get_logs_dir(capability_name)
        if log_path.suffix:
            log_file_path = log_path
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_file_path = Path(log_path) / "{time:YYYY-MM-DD}.log"
        logger.add(
            str(log_file_path),
            rotation="1 day",
            retention="30 days",
            level="DEBUG",
            colorize=False,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | "
                "{name}:{function}:{line} - {message}"
            ),
            encoding="utf-8",
        )


def setup(*, name: str, debug: bool = False, log_file: bool = False) -> None:
    """兼容旧能力入口的初始化别名。"""
    configure_diagnostics(capability_name=name, debug=debug, log_file=log_file)

