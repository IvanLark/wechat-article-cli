"""Click 绑定辅助。"""

from __future__ import annotations

from collections.abc import Callable

import click

from wechat_article_cli._toolkit.cli.common_options import (
    debug_options,
    dry_run_option,
    output_file_option,
    structured_output_options,
)
from wechat_article_cli._toolkit.describe.help import (
    write_capability_epilog,
    write_capability_help,
    write_command_epilog,
    write_command_help,
)
from wechat_article_cli._toolkit.describe.spec import CapabilitySpec, CommandSpec


class AgentCommand(click.Command):
    def __init__(self, *args, help_spec: CommandSpec | None = None, **kwargs):
        self.help_spec = help_spec
        super().__init__(*args, **kwargs)

    def format_help_text(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help_spec is None:
            super().format_help_text(ctx, formatter)
            return
        write_command_help(formatter, self.help_spec)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help_spec is None:
            super().format_epilog(ctx, formatter)
            return
        write_command_epilog(formatter, self.help_spec)


class AgentGroup(click.Group):
    def __init__(self, *args, help_spec: CapabilitySpec | CommandSpec | None = None, **kwargs):
        self.help_spec = help_spec
        super().__init__(*args, **kwargs)

    def format_help_text(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help_spec is None:
            super().format_help_text(ctx, formatter)
            return
        if isinstance(self.help_spec, CapabilitySpec):
            write_capability_help(formatter, self.help_spec)
        else:
            write_command_help(formatter, self.help_spec)

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if self.help_spec is None:
            super().format_epilog(ctx, formatter)
            return
        if isinstance(self.help_spec, CapabilitySpec):
            write_capability_epilog(formatter, self.help_spec)
        else:
            write_command_epilog(formatter, self.help_spec)


def apply_common_options(command: Callable) -> Callable:
    command = structured_output_options(command)
    command = output_file_option(command)
    command = dry_run_option(command)
    command = debug_options(command)
    return command


def command_help_kwargs(spec: CommandSpec) -> dict:
    return {
        "cls": AgentCommand,
        "help_spec": spec,
        "help": spec.summary,
        "short_help": spec.summary,
    }


def capability_help_kwargs(spec: CapabilitySpec) -> dict:
    return {
        "cls": AgentGroup,
        "help_spec": spec,
        "help": spec.summary,
        "short_help": spec.summary,
    }


def group_help_kwargs(spec: CommandSpec) -> dict:
    return {
        "cls": AgentGroup,
        "help_spec": spec,
        "help": spec.summary,
        "short_help": spec.summary,
    }
