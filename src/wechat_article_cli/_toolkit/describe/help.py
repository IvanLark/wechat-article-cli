"""帮助信息格式化。"""

from __future__ import annotations

from click.formatting import HelpFormatter

from wechat_article_cli._toolkit.describe.spec import CapabilitySpec, CommandSpec


def _write_bullet_section(formatter: HelpFormatter, title: str, lines: list[str]) -> None:
    if not lines:
        return
    with formatter.section(title):
        for line in lines:
            formatter.write_text(f"- {line}")


def _write_env_section(formatter: HelpFormatter, spec: CommandSpec) -> None:
    if not spec.env:
        return
    with formatter.section("环境依赖"):
        rows = []
        for item in spec.env:
            label = item.name
            suffix = "required" if item.required else "optional"
            if item.description:
                rows.append((label, f"{item.description} ({suffix})"))
            else:
                rows.append((label, suffix))
        formatter.write_dl(rows, col_max=22, col_spacing=4)


def write_command_help(formatter: HelpFormatter, spec: CommandSpec) -> None:
    formatter.write_paragraph()
    with formatter.indentation():
        formatter.write_text(spec.summary)
        if spec.description:
            formatter.write_paragraph()
            formatter.write_text(spec.description)
    if spec.when_to_use:
        with formatter.section("适用场景"):
            formatter.write_text(spec.when_to_use)
    _write_bullet_section(formatter, "前置条件", list(spec.prerequisites))
    _write_env_section(formatter, spec)


def write_command_epilog(formatter: HelpFormatter, spec: CommandSpec) -> None:
    if spec.examples:
        with formatter.section("示例"):
            formatter.write_dl(
                [(example.command, example.description) for example in spec.examples],
                col_max=40,
                col_spacing=4,
            )
    _write_bullet_section(formatter, "下一步", list(spec.next_steps))
    _write_bullet_section(formatter, "失败恢复", list(spec.failure_recovery))


def write_capability_help(formatter: HelpFormatter, spec: CapabilitySpec) -> None:
    formatter.write_paragraph()
    with formatter.indentation():
        formatter.write_text(spec.summary)
        if spec.description:
            formatter.write_paragraph()
            formatter.write_text(spec.description)
    if spec.background:
        with formatter.section("背景"):
            formatter.write_text(spec.background)
    if spec.when_to_use:
        with formatter.section("适用场景"):
            formatter.write_text(spec.when_to_use)


def write_capability_epilog(formatter: HelpFormatter, spec: CapabilitySpec) -> None:
    if spec.quick_start:
        with formatter.section("快速开始"):
            formatter.write_dl(
                [(example.command, example.description) for example in spec.quick_start],
                col_max=40,
                col_spacing=4,
            )
    _write_bullet_section(formatter, "下一步", list(spec.next_steps))


def format_help_summary(spec: CommandSpec) -> str:
    return f"{spec.path}: {spec.summary}"


def format_help_json(spec: CommandSpec) -> dict:
    return spec.model_dump(mode="json", exclude_none=True)
