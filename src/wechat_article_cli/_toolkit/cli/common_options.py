"""Click 公共选项。"""

from __future__ import annotations

import sys
from collections.abc import Callable

import click


def structured_output_options(command: Callable) -> Callable:
    command = click.option("--compact", is_flag=True, help="输出紧凑 JSON。")(command)
    command = click.option("--yaml", "as_yaml", is_flag=True, help="输出 YAML。")(command)
    command = click.option("--json", "as_json", is_flag=True, help="输出 JSON。")(command)
    return command


def debug_options(command: Callable) -> Callable:
    command = click.option("--verbose", is_flag=True, help="输出详细诊断信息。")(command)
    command = click.option("--debug", is_flag=True, help="输出调试日志。")(command)
    return command


def output_file_option(command: Callable) -> Callable:
    return click.option("--output", type=str, help="输出到指定文件。")(command)


def dry_run_option(command: Callable) -> Callable:
    return click.option("--dry-run", is_flag=True, help="仅做本地校验，不执行副作用。")(command)


def resolve_output_mode(
    *,
    as_json: bool = False,
    as_yaml: bool = False,
    stream: bool = False,
) -> str:
    if as_json and as_yaml:
        raise click.UsageError("不能同时使用 --json 和 --yaml。")
    if stream:
        return "ndjson"
    if as_yaml:
        return "yaml"
    if as_json:
        return "json"
    if not sys.stdout.isatty():
        return "json"
    return "human"
