"""wechat_article CLI。"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError as PydanticValidationError

from wechat_article_cli._toolkit.cli.click_bindings import (
    capability_help_kwargs,
    command_help_kwargs,
    group_help_kwargs,
)
from wechat_article_cli._toolkit.cli.common_options import (
    debug_options,
    output_file_option,
    resolve_output_mode,
    structured_output_options,
)
from wechat_article_cli._toolkit.cli.context import CommandContext
from wechat_article_cli._toolkit.describe.doctor import run_doctor
from wechat_article_cli._toolkit.describe.inspect import build_inspect_report
from wechat_article_cli._toolkit.describe.schema import build_schema_report
from wechat_article_cli._toolkit.protocol.errors import ToolError, ValidationError
from wechat_article_cli._toolkit.protocol.output import failure, print_json, print_yaml, success
from wechat_article_cli._toolkit.runtime.diagnostics import setup as setup_logging
from wechat_article_cli._toolkit.runtime.home import get_capability_home, get_data_dir
from wechat_article_cli.capability import (
    CAPABILITY_NAME,
    CLI_NAME,
    INSPECTABLE_COMMANDS,
    build_doctor_checks,
    get_capability_spec,
    get_command_spec,
)
from wechat_article_cli.models import (
    AccountAddInput,
    AccountAddOutput,
    AccountExportInput,
    AccountExportOutput,
    AccountImportInput,
    AccountImportOutput,
    AccountListInput,
    AccountListOutput,
    AccountRecord,
    AccountRemoveInput,
    AccountRemoveOutput,
    AccountSearchInput,
    AccountSearchOutput,
    ArticleBatch,
    ArticleContentInput,
    ArticleContentOutput,
    ArticleListInput,
    ArticleListOutput,
    ArticleSummary,
    AuthCheckOutput,
    AuthConfirmOutput,
    AuthStartOutput,
    ConfigMutationOutput,
    ConfigPathOutput,
    ConfigSetInput,
    ConfigShowOutput,
    ConfigUnsetInput,
    DoctorPayload,
    GroupAddInput,
    GroupAddOutput,
    GroupCreateInput,
    GroupCreateOutput,
    GroupDeleteInput,
    GroupDeleteOutput,
    GroupExportInput,
    GroupExportOutput,
    GroupImportInput,
    GroupImportOutput,
    GroupListOutput,
    GroupRecord,
    GroupRemoveInput,
    GroupRemoveOutput,
    LibraryExportInput,
    LibraryExportOutput,
    LibraryImportInput,
    LibraryImportOutput,
    RunExportInput,
    RunExportOutput,
    RunIdInput,
    RunListOutput,
    RunRecord,
    RunStatusOutput,
    TaskCreateInput,
    TaskCreateOutput,
    TaskIdInput,
    TaskInfoOutput,
    TaskListOutput,
    TaskRecord,
    TaskRunOutput,
)


def _build_context(
    *,
    command_path: str,
    as_json: bool = False,
    as_yaml: bool = False,
    debug: bool = False,
    verbose: bool = False,
) -> CommandContext:
    return CommandContext(
        capability_name=CAPABILITY_NAME,
        command_path=command_path,
        output_mode=resolve_output_mode(as_json=as_json, as_yaml=as_yaml),
        debug=debug,
        verbose=verbose,
        capability_home=get_capability_home(CAPABILITY_NAME),
        is_tty=sys.stdout.isatty(),
    )


def _build_click_context(
    click_ctx: click.Context,
    *,
    command_path: str,
    as_json: bool = False,
    as_yaml: bool = False,
) -> CommandContext:
    return _build_context(
        command_path=command_path,
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(click_ctx.obj.get("debug")),
        verbose=bool(click_ctx.obj.get("verbose")),
    )


def _emit_output(payload, ctx: CommandContext, *, compact: bool = False, human_renderer=None) -> None:
    if ctx.output_mode == "json":
        print_json(payload, compact=compact)
        return
    if ctx.output_mode == "yaml":
        print_yaml(payload)
        return
    if human_renderer is None:
        click.echo(payload)
        return
    human_renderer(payload)


def _emit_result(
    result: Any,
    ctx: CommandContext,
    *,
    compact: bool = False,
    human_renderer=None,
) -> None:
    if ctx.output_mode in {"json", "yaml"}:
        _emit_output(success(result), ctx, compact=compact)
        return
    _emit_output(result, ctx, compact=compact, human_renderer=human_renderer)


def _emit_failure(ctx: CommandContext, exc: Exception, *, compact: bool = False) -> None:
    if isinstance(exc, PydanticValidationError):
        exc = ValidationError(str(exc))

    if isinstance(exc, ToolError):
        payload = exc.to_envelope().model_dump(mode="json", exclude_none=True)
        exit_code = exc.exit_code
        message = exc.message
    else:
        message = _format_exception(exc)
        payload = failure("wechat_article_failed", message)
        exit_code = 1

    if ctx.output_mode == "json":
        print_json(payload, compact=compact)
    elif ctx.output_mode == "yaml":
        print_yaml(payload)
    else:
        click.echo(message, err=True)
    raise SystemExit(exit_code)


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return f"{type(exc).__name__}（无错误详情）"


def _run_legacy_command(handler, *args) -> None:
    try:
        handler(*args)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        click.echo(_format_exception(exc), err=True)
        raise SystemExit(1) from exc


def _route_logs_to_stderr(*, debug: bool = False, verbose: bool = False) -> None:
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        colorize=False,
        format="{message}",
        filter=lambda record: record["level"].name in {"INFO", "SUCCESS"},
    )
    logger.add(sys.stderr, level="WARNING", colorize=False, format="{message}")
    if debug or verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            colorize=False,
            format="{time:HH:mm:ss} | {level:<7} | {name} - {message}",
            filter=lambda record: record["level"].name == "DEBUG",
        )


def _split_names(names: str) -> list[str]:
    values = [item.strip() for item in names.split(",") if item.strip()]
    if not values:
        raise ValueError("请指定公众号名称")
    return values


def _account_payload(account) -> dict[str, Any]:
    return {
        "fakeid": account.fakeid,
        "name": account.name,
        "avatar": account.avatar,
        "signature": account.signature,
        "added_at": account.added_at,
    }


def _account_record(account) -> AccountRecord:
    return AccountRecord(**_account_payload(account))


def _search_account_payload(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "fakeid": account.get("fakeid", ""),
        "name": account.get("name", ""),
        "avatar": account.get("avatar"),
        "signature": account.get("signature"),
    }


def _search_account_record(account: dict[str, Any]) -> AccountRecord:
    return AccountRecord(**_search_account_payload(account))


def _group_payload(group) -> dict[str, Any]:
    return {
        "name": group.name,
        "accounts": list(group.accounts),
        "account_count": len(group.accounts),
    }


def _group_record(group) -> GroupRecord:
    return GroupRecord(**_group_payload(group))


def _task_payload(task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "name": task.name,
        "created_at": task.created_at,
        "config": task.config.model_dump(mode="json"),
    }


def _task_record(task) -> TaskRecord:
    return TaskRecord(**_task_payload(task))


def _run_payload(run) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "task_id": run.task_id,
        "status": run.status,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "config": run.config.model_dump(mode="json"),
        "progress": [item.model_dump(mode="json") for item in run.progress],
        "statistics": run.statistics.model_dump(mode="json"),
        "articles": run.articles,
    }


def _run_record(run) -> RunRecord:
    return RunRecord(**_run_payload(run))


def _parse_task_create_args(raw_args: tuple[str, ...]) -> dict[str, Any]:
    group = None
    accounts: list[str] = []
    name = ""
    count = 5
    interval = 10.0
    after_date = None
    fetch_content = True
    concurrency = 3

    args = list(raw_args)
    i = 0
    while i < len(args):
        if args[i] == "--group" and i + 1 < len(args):
            group = args[i + 1]
            i += 2
        elif args[i] == "--accounts" and i + 1 < len(args):
            accounts = _split_names(args[i + 1])
            i += 2
        elif args[i] == "--name" and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        elif args[i] == "--count" and i + 1 < len(args):
            count = int(args[i + 1])
            i += 2
        elif args[i] == "--interval" and i + 1 < len(args):
            interval = float(args[i + 1])
            i += 2
        elif args[i] == "--after" and i + 1 < len(args):
            after_date = args[i + 1]
            i += 2
        elif args[i] == "--no-content":
            fetch_content = False
            i += 1
        elif args[i] == "--concurrency" and i + 1 < len(args):
            concurrency = int(args[i + 1])
            i += 2
        else:
            raise ValueError(f"未知参数: {args[i]}")

    return {
        "group_name": group,
        "accounts": accounts or None,
        "name": name,
        "article_count": count,
        "account_interval": interval,
        "after_date": after_date,
        "fetch_content": fetch_content,
        "content_concurrency": concurrency,
    }


def _render_human_auth_start(result: AuthStartOutput) -> None:
    click.echo("二维码已生成")
    click.echo(f"二维码路径：{result.qrcode_path}")
    click.echo("请将二维码展示给用户，让用户使用微信扫描登录")
    click.echo("二维码有效期约 5 分钟")
    click.echo(f"用户扫码确认后，请执行: {CLI_NAME} auth confirm")


def _render_human_auth_confirm(result: AuthConfirmOutput) -> None:
    if result.status == "waiting":
        click.echo("状态：等待扫码")
        if result.qrcode_path:
            click.echo(f"二维码：{result.qrcode_path}")
    elif result.status == "scanned":
        click.echo("状态：已扫码，等待确认")
        click.echo(f"确认后再次执行: {CLI_NAME} auth confirm")
    elif result.status == "confirmed":
        click.echo("登录成功")
        if result.expires_at:
            click.echo(f"凭证有效期至：{result.expires_at}")
    elif result.status == "expired":
        click.echo("二维码已过期")
        click.echo(f"请执行 {CLI_NAME} auth start 重新生成二维码")
    elif result.status == "no_email":
        click.echo("该微信账号未绑定邮箱，无法登录公众号后台")
    else:
        click.echo(f"未知状态：{result.raw_status or result.status}")


def _render_human_auth_check(result: AuthCheckOutput) -> None:
    click.echo(f"状态：{result.status}")
    if result.created_at:
        click.echo(f"登录时间：{result.created_at}")
    if result.expires_at:
        click.echo(f"过期时间：{result.expires_at}")
    if result.remaining_seconds is not None:
        click.echo(f"剩余有效期：{result.remaining_seconds} 秒")


def _render_human_config_path(result: ConfigPathOutput) -> None:
    click.echo(result.path)


def _render_human_config_show(result: ConfigShowOutput) -> None:
    click.echo(f"配置文件：{result.path}")
    click.echo(f"文件存在：{'yes' if result.exists else 'no'}")
    click.echo("")
    click.echo("生效配置：")
    print_yaml(result.effective)
    click.echo("来源：")
    print_yaml(result.sources)


def _render_human_config_mutation(result: ConfigMutationOutput) -> None:
    if result.action == "set":
        click.echo(f"已设置 {result.key}")
        if result.value is not None:
            click.echo("当前值：")
            print_yaml(result.value)
    else:
        click.echo(f"已删除 {result.key}")
    click.echo(f"配置文件：{result.path}")


def _render_human_library_import(result: LibraryImportOutput) -> None:
    click.echo("公众号库导入完成")
    click.echo(f"文件：{result.json_path}")
    click.echo("账号：")
    click.echo(f"  新增：{result.accounts.imported}")
    click.echo(f"  更新：{result.accounts.updated}")
    click.echo(f"  跳过：{result.accounts.skipped}")
    click.echo(f"  无效：{result.accounts.invalid}")
    click.echo("分组：")
    click.echo(f"  新增：{result.groups.imported}")
    click.echo(f"  更新：{result.groups.updated}")
    click.echo(f"  跳过：{result.groups.skipped}")
    click.echo(f"  无效分组：{result.groups.invalid}")
    click.echo(f"  无效成员：{result.groups.invalid_accounts}")
    click.echo(f"  当前分组总数：{result.groups.total_groups}")
    if result.groups.missing_accounts:
        click.echo("分组中有成员缺少账号详情，已跳过：")
        click.echo("  " + "、".join(result.groups.missing_accounts))


def _render_human_library_export(result: LibraryExportOutput) -> None:
    click.echo("公众号库已导出")
    click.echo(f"文件：{result.json_path}")
    click.echo(f"账号：{result.exported_accounts}")
    click.echo(f"分组：{result.exported_groups}")


def _render_human_article_list(result: ArticleListOutput) -> None:
    if not result.batches:
        click.echo("暂无文章")
        return
    for batch in result.batches:
        click.echo(f"公众号「{batch.account_name}」共 {len(batch.items)} 篇文章：")
        for item in batch.items:
            click.echo("")
            click.echo(f"标题：{item.title}")
            click.echo(f"日期：{item.create_date}")
            click.echo(f"链接：{item.link}")
            if item.author:
                click.echo(f"作者：{item.author}")
            if item.digest:
                click.echo(f"摘要：{item.digest}")
        click.echo("")
    click.echo(f"总文章数：{result.total_articles}")


def _render_human_article_content(result: ArticleContentOutput) -> None:
    source = "缓存" if result.cached else "网络"
    click.echo(f"文章获取成功（来源：{source}）")
    click.echo(f"标题：{result.title}")
    if result.author:
        click.echo(f"作者：{result.author}")
    if result.publish_date:
        click.echo(f"日期：{result.publish_date}")
    click.echo(f"格式：{result.format}")
    click.echo(f"输出路径：{result.output_path}")
    click.echo(f"内容长度：{result.content_length} 字符")


def _render_human_doctor(payload: DoctorPayload) -> None:
    click.echo(f"auth_status: {payload.auth_status}")
    click.echo(f"proxy_configured: {'yes' if payload.proxy_configured else 'no'}")
    click.echo(f"proxy_count: {payload.proxy_count}")
    click.echo(f"accounts: {payload.account_count}")
    click.echo(f"groups: {payload.group_count}")
    click.echo(f"tasks: {payload.task_count}")
    click.echo(f"runs: {payload.run_count}")
    click.echo("")
    click.echo("Checks:")
    for check in payload.checks:
        status = "ok" if check.ok else "failed"
        click.echo(f"- {check.name}: {status} - {check.message}")
        if check.hint:
            click.echo(f"  {check.hint}")


def _render_human_inspect(report) -> None:
    click.echo(report.path)
    click.echo(report.summary)
    if report.description:
        click.echo("")
        click.echo(report.description)
    if report.env:
        click.echo("")
        click.echo("环境依赖：")
        for item in report.env:
            required = "required" if item.get("required", True) else "optional"
            click.echo(f"- {item['name']} ({required})")
            if item.get("description"):
                click.echo(f"  {item['description']}")
    if report.examples:
        click.echo("")
        click.echo("示例：")
        for example in report.examples:
            click.echo(f"- {example['command']}")
            if example.get("description"):
                click.echo(f"  {example['description']}")


def _render_human_schema(report) -> None:
    click.echo(f"command: {report.command}")
    click.echo("")
    click.echo("input_schema:")
    print_yaml(report.input_schema or {})
    click.echo("output_schema:")
    print_yaml(report.output_schema or {})


def _safe_filename(title: str, link: str, ext: str) -> str:
    safe = re.sub(r"[^\u4e00-\u9fff\w\-]", "", title)[:20]
    safe = safe.strip("._- ") or "article"
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    return f"{safe}_{link_hash}{ext}"


@click.group(**capability_help_kwargs(get_capability_spec()))
@debug_options
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool) -> None:
    setup_logging(name=CAPABILITY_NAME, debug=debug or verbose)
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["verbose"] = verbose


@cli.group("auth", **group_help_kwargs(get_command_spec("auth")))
def auth_group() -> None:
    pass


@auth_group.command("start", **command_help_kwargs(get_command_spec("auth.start")))
@structured_output_options
@click.pass_context
def auth_start_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.service import start_auth

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.auth.start",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        result = AuthStartOutput(qrcode_path=asyncio.run(start_auth()))
        _emit_result(result, command_ctx, compact=compact, human_renderer=_render_human_auth_start)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@auth_group.command("confirm", **command_help_kwargs(get_command_spec("auth.confirm")))
@structured_output_options
@click.pass_context
def auth_confirm_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.service import confirm_auth

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.auth.confirm",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        result = AuthConfirmOutput.model_validate(asyncio.run(confirm_auth()))
        _emit_result(result, command_ctx, compact=compact, human_renderer=_render_human_auth_confirm)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@auth_group.command("check", **command_help_kwargs(get_command_spec("auth.check")))
@structured_output_options
@click.pass_context
def auth_check_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.service import check_auth

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.auth.check",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        result = AuthCheckOutput.model_validate(check_auth())
        _emit_result(result, command_ctx, compact=compact, human_renderer=_render_human_auth_check)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("config", **group_help_kwargs(get_command_spec("config")))
def config_group() -> None:
    pass


@config_group.command("path", **command_help_kwargs(get_command_spec("config.path")))
@structured_output_options
@click.pass_context
def config_path_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.config import build_config_path_payload

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.config.path",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        result = ConfigPathOutput(**build_config_path_payload())
        _emit_result(result, command_ctx, compact=compact, human_renderer=_render_human_config_path)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@config_group.command("show", **command_help_kwargs(get_command_spec("config.show")))
@structured_output_options
@click.pass_context
def config_show_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.config import build_config_show_payload

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.config.show",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        result = ConfigShowOutput(**build_config_show_payload())
        _emit_result(result, command_ctx, compact=compact, human_renderer=_render_human_config_show)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@config_group.command("set", **command_help_kwargs(get_command_spec("config.set")))
@click.argument("key")
@click.argument("value")
@structured_output_options
@click.pass_context
def config_set_command(
    ctx: click.Context,
    key: str,
    value: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.config import set_config_value

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.config.set",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        input_model = ConfigSetInput(key=key, value=value)
        result = ConfigMutationOutput(**set_config_value(input_model.key, input_model.value))
        _emit_result(
            result,
            command_ctx,
            compact=compact,
            human_renderer=_render_human_config_mutation,
        )
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@config_group.command("unset", **command_help_kwargs(get_command_spec("config.unset")))
@click.argument("key")
@structured_output_options
@click.pass_context
def config_unset_command(
    ctx: click.Context,
    key: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.config import unset_config_value

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.config.unset",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        input_model = ConfigUnsetInput(key=key)
        result = ConfigMutationOutput(**unset_config_value(input_model.key))
        _emit_result(
            result,
            command_ctx,
            compact=compact,
            human_renderer=_render_human_config_mutation,
        )
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("article", **group_help_kwargs(get_command_spec("article")))
def article_group() -> None:
    pass


@article_group.command("list", **command_help_kwargs(get_command_spec("article.list")))
@click.argument("name", required=False)
@click.option("--group", "group_name")
@click.option("--count", default=5, type=int)
@click.option("--offset", default=0, type=int)
@structured_output_options
@click.pass_context
def article_list_command(
    ctx: click.Context,
    name: str | None,
    group_name: str | None,
    count: int,
    offset: int,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.service import list_articles

    command_ctx = _build_context(
        command_path="wechat_article.article.list",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        input_model = ArticleListInput(name=name, group_name=group_name, count=count, offset=offset)
        raw = asyncio.run(
            list_articles(
                name=input_model.name,
                group_name=input_model.group_name,
                count=input_model.count,
                offset=input_model.offset,
            )
        )
        batches = [
            ArticleBatch(account_name=account_name, items=[ArticleSummary(**item) for item in articles])
            for account_name, articles in raw
        ]
        result = ArticleListOutput(batches=batches, total_articles=sum(len(batch.items) for batch in batches))
        payload = success(result)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(payload, command_ctx, compact=compact)
        else:
            _emit_output(result, command_ctx, compact=compact, human_renderer=_render_human_article_list)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@article_group.command("content", **command_help_kwargs(get_command_spec("article.content")))
@click.argument("link")
@click.option("--format", "fmt", default="md", type=click.Choice(["md", "markdown", "html", "text"]))
@output_file_option
@structured_output_options
@click.pass_context
def article_content_command(
    ctx: click.Context,
    link: str,
    fmt: str,
    output: str | None,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.service import get_content

    command_ctx = _build_context(
        command_path="wechat_article.article.content",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        input_model = ArticleContentInput(link=link, fmt=fmt, output=output)
        result_raw = asyncio.run(get_content(input_model.link, fmt=input_model.fmt))
        if input_model.output:
            out_path = Path(input_model.output)
        else:
            ext = {"markdown": ".md", "html": ".html", "text": ".txt"}[result_raw["format"]]
            export_dir = get_data_dir(CAPABILITY_NAME) / "exports" / "articles"
            export_dir.mkdir(parents=True, exist_ok=True)
            out_path = export_dir / _safe_filename(result_raw["title"], input_model.link, ext)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result_raw["content"], encoding="utf-8")
        result = ArticleContentOutput(
            title=result_raw["title"],
            author=result_raw.get("author"),
            publish_date=result_raw.get("publish_date"),
            format=result_raw["format"],
            content=result_raw["content"],
            output_path=str(out_path.resolve()),
            cached=bool(result_raw.get("cached")),
            content_length=len(result_raw["content"]),
        )
        payload = success(result)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(payload, command_ctx, compact=compact)
        else:
            _emit_output(result, command_ctx, compact=compact, human_renderer=_render_human_article_content)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("account", **group_help_kwargs(get_command_spec("account")))
def account_group() -> None:
    pass


@account_group.command("list", **command_help_kwargs(get_command_spec("account.list")))
@click.option("--group", "group_name")
@structured_output_options
@click.pass_context
def account_list_command(
    ctx: click.Context,
    group_name: str | None,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_list
    from wechat_article_cli.service import list_accounts

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.list",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_list, group_name)
            return
        accounts = list_accounts(group_name)
        result = AccountListOutput(
            group_name=group_name,
            accounts=[_account_record(account) for account in accounts],
            total_accounts=len(accounts),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@account_group.command("search", **command_help_kwargs(get_command_spec("account.search")))
@click.argument("query")
@structured_output_options
@click.pass_context
def account_search_command(
    ctx: click.Context,
    query: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_search
    from wechat_article_cli.service import search_accounts

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.search",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_search, query)
            return
        accounts = asyncio.run(search_accounts(query))
        result = AccountSearchOutput(
            query=query,
            accounts=[_search_account_record(account) for account in accounts],
            total_accounts=len(accounts),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@account_group.command("add", **command_help_kwargs(get_command_spec("account.add")))
@click.argument("names")
@structured_output_options
@click.pass_context
def account_add_command(
    ctx: click.Context,
    names: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_add
    from wechat_article_cli.service import add_accounts

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.add",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_add, names)
            return
        result_raw = add_accounts(_split_names(names))
        result = AccountAddOutput(
            **result_raw,
            added_count=len(result_raw["added"]),
            skipped_count=len(result_raw["skipped"]),
            not_found_count=len(result_raw["not_found"]),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@account_group.command("remove", **command_help_kwargs(get_command_spec("account.remove")))
@click.argument("name")
@structured_output_options
@click.pass_context
def account_remove_command(
    ctx: click.Context,
    name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_remove
    from wechat_article_cli.service import remove_account

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.remove",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_remove, name)
            return
        remove_account(name)
        _emit_result(AccountRemoveOutput(name=name), command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@account_group.command("import", **command_help_kwargs(get_command_spec("account.import")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def account_import_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_import
    from wechat_article_cli.service import import_accounts_from_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.import",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_import, json_path)
            return
        input_model = AccountImportInput(json_path=json_path)
        result_raw = import_accounts_from_json(input_model.json_path)
        result = AccountImportOutput(json_path=str(Path(input_model.json_path).expanduser().resolve()), **result_raw)
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@account_group.command("export", **command_help_kwargs(get_command_spec("account.export")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def account_export_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_account import cmd_export
    from wechat_article_cli.service import export_accounts_to_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.account.export",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_export, json_path)
            return
        input_model = AccountExportInput(json_path=json_path)
        result = AccountExportOutput(**export_accounts_to_json(input_model.json_path))
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("library", **group_help_kwargs(get_command_spec("library")))
def library_group() -> None:
    pass


@library_group.command("import", **command_help_kwargs(get_command_spec("library.import")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def library_import_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.service import import_library_from_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.library.import",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        input_model = LibraryImportInput(json_path=json_path)
        result = LibraryImportOutput(**import_library_from_json(input_model.json_path))
        _emit_result(
            result,
            command_ctx,
            compact=compact,
            human_renderer=_render_human_library_import,
        )
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@library_group.command("export", **command_help_kwargs(get_command_spec("library.export")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def library_export_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.service import export_library_to_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.library.export",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        input_model = LibraryExportInput(json_path=json_path)
        result = LibraryExportOutput(**export_library_to_json(input_model.json_path))
        _emit_result(
            result,
            command_ctx,
            compact=compact,
            human_renderer=_render_human_library_export,
        )
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("group", **group_help_kwargs(get_command_spec("group")))
def group_group() -> None:
    pass


@group_group.command("list", **command_help_kwargs(get_command_spec("group.list")))
@structured_output_options
@click.pass_context
def group_list_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.cmd_group import cmd_list
    from wechat_article_cli.service import list_groups

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.list",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_list)
            return
        groups = list_groups()
        result = GroupListOutput(
            groups=[_group_record(group) for group in groups],
            total_groups=len(groups),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("import", **command_help_kwargs(get_command_spec("group.import")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def group_import_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_import
    from wechat_article_cli.service import import_groups_from_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.import",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_import, json_path)
            return
        input_model = GroupImportInput(json_path=json_path)
        result_raw = import_groups_from_json(input_model.json_path)
        result = GroupImportOutput(
            json_path=str(Path(input_model.json_path).expanduser().resolve()),
            **result_raw,
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("export", **command_help_kwargs(get_command_spec("group.export")))
@click.argument("json_path")
@structured_output_options
@click.pass_context
def group_export_command(
    ctx: click.Context,
    json_path: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_export
    from wechat_article_cli.service import export_groups_to_json

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.export",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_export, json_path)
            return
        input_model = GroupExportInput(json_path=json_path)
        result = GroupExportOutput(**export_groups_to_json(input_model.json_path))
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("create", **command_help_kwargs(get_command_spec("group.create")))
@click.argument("name")
@structured_output_options
@click.pass_context
def group_create_command(
    ctx: click.Context,
    name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_create
    from wechat_article_cli.service import create_group

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.create",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_create, name)
            return
        create_group(name)
        _emit_result(GroupCreateOutput(name=name), command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("delete", **command_help_kwargs(get_command_spec("group.delete")))
@click.argument("name")
@structured_output_options
@click.pass_context
def group_delete_command(
    ctx: click.Context,
    name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_delete
    from wechat_article_cli.service import delete_group

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.delete",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_delete, name)
            return
        removed_accounts = delete_group(name)
        result = GroupDeleteOutput(name=name, removed_accounts=removed_accounts)
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("add", **command_help_kwargs(get_command_spec("group.add")))
@click.argument("group_name")
@click.argument("names")
@structured_output_options
@click.pass_context
def group_add_command(
    ctx: click.Context,
    group_name: str,
    names: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_add
    from wechat_article_cli.service import add_to_group

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.add",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_add, group_name, names)
            return
        result_raw = add_to_group(group_name, _split_names(names))
        result = GroupAddOutput(
            group_name=group_name,
            **result_raw,
            added_count=len(result_raw["added"]),
            skipped_count=len(result_raw["skipped"]),
            not_in_lib_count=len(result_raw["not_in_lib"]),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@group_group.command("remove", **command_help_kwargs(get_command_spec("group.remove")))
@click.argument("group_name")
@click.argument("name")
@structured_output_options
@click.pass_context
def group_remove_command(
    ctx: click.Context,
    group_name: str,
    name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_group import cmd_remove_account
    from wechat_article_cli.service import remove_from_group

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.group.remove",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_remove_account, group_name, name)
            return
        remove_from_group(group_name, name)
        result = GroupRemoveOutput(group_name=group_name, name=name)
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("task", **group_help_kwargs(get_command_spec("task")))
def task_group() -> None:
    pass


@task_group.command("create", context_settings={"ignore_unknown_options": True}, **command_help_kwargs(get_command_spec("task.create")))
@click.argument("raw_args", nargs=-1, type=click.UNPROCESSED)
@structured_output_options
@click.pass_context
def task_create_command(
    ctx: click.Context,
    raw_args: tuple[str, ...],
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_task import cmd_create
    from wechat_article_cli.service import create_task

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.task.create",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_create, list(raw_args))
            return
        kwargs = _parse_task_create_args(raw_args)
        task = create_task(**kwargs)
        _emit_result(TaskCreateOutput(task=_task_record(task)), command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@task_group.command("list", **command_help_kwargs(get_command_spec("task.list")))
@structured_output_options
@click.pass_context
def task_list_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.cmd_task import cmd_list
    from wechat_article_cli.service import get_all_tasks

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.task.list",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_list, [])
            return
        tasks = get_all_tasks()
        result = TaskListOutput(tasks=[_task_record(task) for task in tasks], total_tasks=len(tasks))
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@task_group.command("info", **command_help_kwargs(get_command_spec("task.info")))
@click.argument("task_id")
@structured_output_options
@click.pass_context
def task_info_command(
    ctx: click.Context,
    task_id: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_task import cmd_info
    from wechat_article_cli.service import get_task

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.task.info",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_info, [task_id])
            return
        task = get_task(task_id)
        _emit_result(TaskInfoOutput(task=_task_record(task)), command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@task_group.command("run", **command_help_kwargs(get_command_spec("task.run")))
@click.argument("task_id")
@structured_output_options
@click.pass_context
def task_run_command(
    ctx: click.Context,
    task_id: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_task import cmd_run
    from wechat_article_cli.service import start_run
    from wechat_article_cli.task_runner import run_task

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.task.run",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_run, [task_id])
            return
        _route_logs_to_stderr(debug=command_ctx.debug, verbose=command_ctx.verbose)
        run = start_run(task_id)
        run = asyncio.run(run_task(run))
        _emit_result(TaskRunOutput(run=_run_record(run)), command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.group("run", **group_help_kwargs(get_command_spec("run")))
def run_group() -> None:
    pass


@run_group.command("list", **command_help_kwargs(get_command_spec("run.list")))
@structured_output_options
@click.pass_context
def run_list_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.cmd_run import cmd_list
    from wechat_article_cli.service import get_all_runs

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.run.list",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_list, [])
            return
        runs = get_all_runs()
        result = RunListOutput(runs=[_run_record(run) for run in runs], total_runs=len(runs))
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@run_group.command("status", **command_help_kwargs(get_command_spec("run.status")))
@click.argument("run_id")
@structured_output_options
@click.pass_context
def run_status_command(
    ctx: click.Context,
    run_id: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_run import cmd_status
    from wechat_article_cli.service import get_run

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.run.status",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_status, [run_id])
            return
        run = get_run(run_id)
        failed_articles = [a for a in run.articles if a.get("content_status") == "failed"]
        result = RunStatusOutput(run=_run_record(run), failed_articles=failed_articles)
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@run_group.command("export", **command_help_kwargs(get_command_spec("run.export")))
@click.argument("run_id")
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "excel"]), default="json")
@structured_output_options
@click.pass_context
def run_export_command(
    ctx: click.Context,
    run_id: str,
    fmt: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    from wechat_article_cli.cmd_run import cmd_export
    from wechat_article_cli.export import export_run
    from wechat_article_cli.service import get_run

    command_ctx = _build_click_context(
        ctx,
        command_path="wechat_article.run.export",
        as_json=as_json,
        as_yaml=as_yaml,
    )
    try:
        if command_ctx.output_mode == "human":
            _run_legacy_command(cmd_export, [run_id, "--format", fmt])
            return
        run = get_run(run_id)
        path = export_run(run, fmt=fmt)
        result = RunExportOutput(
            run_id=run.run_id,
            format=fmt,
            path=str(path),
            article_count=len(run.articles),
        )
        _emit_result(result, command_ctx, compact=compact)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.command("doctor", **command_help_kwargs(get_command_spec("doctor")))
@structured_output_options
@click.pass_context
def doctor_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    command_ctx = _build_context(
        command_path="wechat_article.doctor",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        report = asyncio.run(run_doctor(CAPABILITY_NAME, build_doctor_checks()))

        from wechat_article_cli.proxy import get_proxy_urls
        from wechat_article_cli.service import check_auth
        from wechat_article_cli.storage import (
            list_run_ids,
            load_all_tasks,
            load_groups,
            load_saved_accounts,
        )

        auth_status = check_auth()["status"]
        proxy_urls = get_proxy_urls()
        saved_accounts = load_saved_accounts()
        groups = load_groups()
        tasks = load_all_tasks()
        runs = list_run_ids()

        payload = DoctorPayload(
            ok=report.ok,
            capability=report.capability,
            auth_status=auth_status,
            proxy_configured=bool(proxy_urls),
            proxy_count=len(proxy_urls),
            account_count=len(saved_accounts.accounts),
            group_count=len(groups.groups),
            task_count=len(tasks),
            run_count=len(runs),
            checks=report.checks,
            summary=report.summary,
        )
        result_payload = success(payload)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(result_payload, command_ctx, compact=compact)
        else:
            _emit_output(payload, command_ctx, compact=compact, human_renderer=_render_human_doctor)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@cli.command("inspect", **command_help_kwargs(get_command_spec("inspect")))
@click.argument("command_name", type=click.Choice(list(INSPECTABLE_COMMANDS)))
@structured_output_options
@click.pass_context
def inspect_command(
    ctx: click.Context,
    command_name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    command_ctx = _build_context(
        command_path="wechat_article.inspect",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    input_model_map = {
        "auth": None,
        "auth.start": None,
        "auth.confirm": None,
        "auth.check": None,
        "config": None,
        "config.path": None,
        "config.show": None,
        "config.set": ConfigSetInput,
        "config.unset": ConfigUnsetInput,
        "account": None,
        "account.list": AccountListInput,
        "account.search": AccountSearchInput,
        "account.add": AccountAddInput,
        "account.remove": AccountRemoveInput,
        "account.import": AccountImportInput,
        "account.export": AccountExportInput,
        "library": None,
        "library.import": LibraryImportInput,
        "library.export": LibraryExportInput,
        "group": None,
        "group.list": None,
        "group.import": GroupImportInput,
        "group.export": GroupExportInput,
        "group.create": GroupCreateInput,
        "group.delete": GroupDeleteInput,
        "group.add": GroupAddInput,
        "group.remove": GroupRemoveInput,
        "article": None,
        "article.list": ArticleListInput,
        "article.content": ArticleContentInput,
        "task": None,
        "task.create": TaskCreateInput,
        "task.list": None,
        "task.info": TaskIdInput,
        "task.run": TaskIdInput,
        "run": None,
        "run.list": None,
        "run.status": RunIdInput,
        "run.export": RunExportInput,
        "doctor": None,
    }
    output_model_map = {
        "auth": None,
        "auth.start": AuthStartOutput,
        "auth.confirm": AuthConfirmOutput,
        "auth.check": AuthCheckOutput,
        "config": None,
        "config.path": ConfigPathOutput,
        "config.show": ConfigShowOutput,
        "config.set": ConfigMutationOutput,
        "config.unset": ConfigMutationOutput,
        "account": None,
        "account.list": AccountListOutput,
        "account.search": AccountSearchOutput,
        "account.add": AccountAddOutput,
        "account.remove": AccountRemoveOutput,
        "account.import": AccountImportOutput,
        "account.export": AccountExportOutput,
        "library": None,
        "library.import": LibraryImportOutput,
        "library.export": LibraryExportOutput,
        "group": None,
        "group.list": GroupListOutput,
        "group.import": GroupImportOutput,
        "group.export": GroupExportOutput,
        "group.create": GroupCreateOutput,
        "group.delete": GroupDeleteOutput,
        "group.add": GroupAddOutput,
        "group.remove": GroupRemoveOutput,
        "article": None,
        "article.list": ArticleListOutput,
        "article.content": ArticleContentOutput,
        "task": None,
        "task.create": TaskCreateOutput,
        "task.list": TaskListOutput,
        "task.info": TaskInfoOutput,
        "task.run": TaskRunOutput,
        "run": None,
        "run.list": RunListOutput,
        "run.status": RunStatusOutput,
        "run.export": RunExportOutput,
        "doctor": DoctorPayload,
    }
    report = build_inspect_report(
        get_command_spec(command_name),
        input_model=input_model_map[command_name],
        output_model=output_model_map[command_name],
    )
    payload = success(report)
    if command_ctx.output_mode in {"json", "yaml"}:
        _emit_output(payload, command_ctx, compact=compact)
    else:
        _emit_output(report, command_ctx, compact=compact, human_renderer=_render_human_inspect)


@cli.command("schema", **command_help_kwargs(get_command_spec("schema")))
@click.argument("command_name", type=click.Choice(list(INSPECTABLE_COMMANDS)))
@structured_output_options
@click.pass_context
def schema_command(
    ctx: click.Context,
    command_name: str,
    as_json: bool,
    as_yaml: bool,
    compact: bool,
) -> None:
    command_ctx = _build_context(
        command_path="wechat_article.schema",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    input_model_map = {
        "auth": None,
        "auth.start": None,
        "auth.confirm": None,
        "auth.check": None,
        "config": None,
        "config.path": None,
        "config.show": None,
        "config.set": ConfigSetInput,
        "config.unset": ConfigUnsetInput,
        "account": None,
        "account.list": AccountListInput,
        "account.search": AccountSearchInput,
        "account.add": AccountAddInput,
        "account.remove": AccountRemoveInput,
        "account.import": AccountImportInput,
        "account.export": AccountExportInput,
        "library": None,
        "library.import": LibraryImportInput,
        "library.export": LibraryExportInput,
        "group": None,
        "group.list": None,
        "group.import": GroupImportInput,
        "group.export": GroupExportInput,
        "group.create": GroupCreateInput,
        "group.delete": GroupDeleteInput,
        "group.add": GroupAddInput,
        "group.remove": GroupRemoveInput,
        "article": None,
        "article.list": ArticleListInput,
        "article.content": ArticleContentInput,
        "task": None,
        "task.create": TaskCreateInput,
        "task.list": None,
        "task.info": TaskIdInput,
        "task.run": TaskIdInput,
        "run": None,
        "run.list": None,
        "run.status": RunIdInput,
        "run.export": RunExportInput,
        "doctor": None,
    }
    output_model_map = {
        "auth": None,
        "auth.start": AuthStartOutput,
        "auth.confirm": AuthConfirmOutput,
        "auth.check": AuthCheckOutput,
        "config": None,
        "config.path": ConfigPathOutput,
        "config.show": ConfigShowOutput,
        "config.set": ConfigMutationOutput,
        "config.unset": ConfigMutationOutput,
        "account": None,
        "account.list": AccountListOutput,
        "account.search": AccountSearchOutput,
        "account.add": AccountAddOutput,
        "account.remove": AccountRemoveOutput,
        "account.import": AccountImportOutput,
        "account.export": AccountExportOutput,
        "library": None,
        "library.import": LibraryImportOutput,
        "library.export": LibraryExportOutput,
        "group": None,
        "group.list": GroupListOutput,
        "group.import": GroupImportOutput,
        "group.export": GroupExportOutput,
        "group.create": GroupCreateOutput,
        "group.delete": GroupDeleteOutput,
        "group.add": GroupAddOutput,
        "group.remove": GroupRemoveOutput,
        "article": None,
        "article.list": ArticleListOutput,
        "article.content": ArticleContentOutput,
        "task": None,
        "task.create": TaskCreateOutput,
        "task.list": TaskListOutput,
        "task.info": TaskInfoOutput,
        "task.run": TaskRunOutput,
        "run": None,
        "run.list": RunListOutput,
        "run.status": RunStatusOutput,
        "run.export": RunExportOutput,
        "doctor": DoctorPayload,
    }
    report = build_schema_report(
        get_command_spec(command_name),
        input_model=input_model_map[command_name],
        output_model=output_model_map[command_name],
    )
    payload = success(report)
    if command_ctx.output_mode in {"json", "yaml"}:
        _emit_output(payload, command_ctx, compact=compact)
    else:
        _emit_output(report, command_ctx, compact=compact, human_renderer=_render_human_schema)


def main(argv: list[str] | None = None) -> None:
    cli.main(args=argv, prog_name=CLI_NAME, standalone_mode=True)
