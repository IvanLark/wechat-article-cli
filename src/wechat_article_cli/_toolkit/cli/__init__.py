"""CLI 框架绑定层。"""

from wechat_article_cli._toolkit.cli.common_options import (
    debug_options,
    dry_run_option,
    output_file_option,
    resolve_output_mode,
    structured_output_options,
)
from wechat_article_cli._toolkit.cli.context import CommandContext

__all__ = [
    "CommandContext",
    "debug_options",
    "dry_run_option",
    "output_file_option",
    "resolve_output_mode",
    "structured_output_options",
]

