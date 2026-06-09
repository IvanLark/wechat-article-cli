"""wechat_article CLI。"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path

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
    ArticleBatch,
    ArticleContentInput,
    ArticleContentOutput,
    ArticleListInput,
    ArticleListOutput,
    ArticleSummary,
    AuthCheckOutput,
    AuthConfirmOutput,
    AuthStartOutput,
    DoctorPayload,
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

    command_ctx = _build_context(
        command_path="wechat_article.auth.start",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        result = AuthStartOutput(qrcode_path=asyncio.run(start_auth()))
        payload = success(result)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(payload, command_ctx, compact=compact)
        else:
            _emit_output(result, command_ctx, compact=compact, human_renderer=_render_human_auth_start)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@auth_group.command("confirm", **command_help_kwargs(get_command_spec("auth.confirm")))
@structured_output_options
@click.pass_context
def auth_confirm_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.service import confirm_auth

    command_ctx = _build_context(
        command_path="wechat_article.auth.confirm",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        result = AuthConfirmOutput.model_validate(asyncio.run(confirm_auth()))
        payload = success(result)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(payload, command_ctx, compact=compact)
        else:
            _emit_output(result, command_ctx, compact=compact, human_renderer=_render_human_auth_confirm)
    except Exception as exc:
        _emit_failure(command_ctx, exc, compact=compact)


@auth_group.command("check", **command_help_kwargs(get_command_spec("auth.check")))
@structured_output_options
@click.pass_context
def auth_check_command(ctx: click.Context, as_json: bool, as_yaml: bool, compact: bool) -> None:
    from wechat_article_cli.service import check_auth

    command_ctx = _build_context(
        command_path="wechat_article.auth.check",
        as_json=as_json,
        as_yaml=as_yaml,
        debug=bool(ctx.obj.get("debug")),
        verbose=bool(ctx.obj.get("verbose")),
    )
    try:
        result = AuthCheckOutput.model_validate(check_auth())
        payload = success(result)
        if command_ctx.output_mode in {"json", "yaml"}:
            _emit_output(payload, command_ctx, compact=compact)
        else:
            _emit_output(result, command_ctx, compact=compact, human_renderer=_render_human_auth_check)
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
def account_list_command(group_name: str | None) -> None:
    from wechat_article_cli.cmd_account import cmd_list

    _run_legacy_command(cmd_list, group_name)


@account_group.command("search", **command_help_kwargs(get_command_spec("account.search")))
@click.argument("query")
def account_search_command(query: str) -> None:
    from wechat_article_cli.cmd_account import cmd_search

    _run_legacy_command(cmd_search, query)


@account_group.command("add", **command_help_kwargs(get_command_spec("account.add")))
@click.argument("names")
def account_add_command(names: str) -> None:
    from wechat_article_cli.cmd_account import cmd_add

    _run_legacy_command(cmd_add, names)


@account_group.command("remove", **command_help_kwargs(get_command_spec("account.remove")))
@click.argument("name")
def account_remove_command(name: str) -> None:
    from wechat_article_cli.cmd_account import cmd_remove

    _run_legacy_command(cmd_remove, name)


@account_group.command("import", **command_help_kwargs(get_command_spec("account.import")))
@click.argument("json_path")
def account_import_command(json_path: str) -> None:
    from wechat_article_cli.cmd_account import cmd_import

    _run_legacy_command(cmd_import, json_path)


@account_group.command("export", **command_help_kwargs(get_command_spec("account.export")))
@click.argument("json_path")
def account_export_command(json_path: str) -> None:
    from wechat_article_cli.cmd_account import cmd_export

    _run_legacy_command(cmd_export, json_path)


@cli.group("group", **group_help_kwargs(get_command_spec("group")))
def group_group() -> None:
    pass


@group_group.command("list", **command_help_kwargs(get_command_spec("group.list")))
def group_list_command() -> None:
    from wechat_article_cli.cmd_group import cmd_list

    _run_legacy_command(cmd_list)


@group_group.command("create", **command_help_kwargs(get_command_spec("group.create")))
@click.argument("name")
def group_create_command(name: str) -> None:
    from wechat_article_cli.cmd_group import cmd_create

    _run_legacy_command(cmd_create, name)


@group_group.command("delete", **command_help_kwargs(get_command_spec("group.delete")))
@click.argument("name")
def group_delete_command(name: str) -> None:
    from wechat_article_cli.cmd_group import cmd_delete

    _run_legacy_command(cmd_delete, name)


@group_group.command("add", **command_help_kwargs(get_command_spec("group.add")))
@click.argument("group_name")
@click.argument("names")
def group_add_command(group_name: str, names: str) -> None:
    from wechat_article_cli.cmd_group import cmd_add

    _run_legacy_command(cmd_add, group_name, names)


@group_group.command("remove", **command_help_kwargs(get_command_spec("group.remove")))
@click.argument("group_name")
@click.argument("name")
def group_remove_command(group_name: str, name: str) -> None:
    from wechat_article_cli.cmd_group import cmd_remove_account

    _run_legacy_command(cmd_remove_account, group_name, name)


@cli.group("task", **group_help_kwargs(get_command_spec("task")))
def task_group() -> None:
    pass


@task_group.command("create", context_settings={"ignore_unknown_options": True}, **command_help_kwargs(get_command_spec("task.create")))
@click.argument("raw_args", nargs=-1, type=click.UNPROCESSED)
def task_create_command(raw_args: tuple[str, ...]) -> None:
    from wechat_article_cli.cmd_task import cmd_create

    _run_legacy_command(cmd_create, list(raw_args))


@task_group.command("list", **command_help_kwargs(get_command_spec("task.list")))
def task_list_command() -> None:
    from wechat_article_cli.cmd_task import cmd_list

    _run_legacy_command(cmd_list, [])


@task_group.command("info", **command_help_kwargs(get_command_spec("task.info")))
@click.argument("task_id")
def task_info_command(task_id: str) -> None:
    from wechat_article_cli.cmd_task import cmd_info

    _run_legacy_command(cmd_info, [task_id])


@task_group.command("run", **command_help_kwargs(get_command_spec("task.run")))
@click.argument("task_id")
def task_run_command(task_id: str) -> None:
    from wechat_article_cli.cmd_task import cmd_run

    _run_legacy_command(cmd_run, [task_id])


@cli.group("run", **group_help_kwargs(get_command_spec("run")))
def run_group() -> None:
    pass


@run_group.command("list", **command_help_kwargs(get_command_spec("run.list")))
def run_list_command() -> None:
    from wechat_article_cli.cmd_run import cmd_list

    _run_legacy_command(cmd_list, [])


@run_group.command("status", **command_help_kwargs(get_command_spec("run.status")))
@click.argument("run_id")
def run_status_command(run_id: str) -> None:
    from wechat_article_cli.cmd_run import cmd_status

    _run_legacy_command(cmd_status, [run_id])


@run_group.command("export", **command_help_kwargs(get_command_spec("run.export")))
@click.argument("run_id")
@click.option("--format", "fmt", type=click.Choice(["json", "csv", "excel"]), default="json")
def run_export_command(run_id: str, fmt: str) -> None:
    from wechat_article_cli.cmd_run import cmd_export

    _run_legacy_command(cmd_export, [run_id, "--format", fmt])


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
        "auth.start": None,
        "auth.confirm": None,
        "auth.check": None,
        "account": None,
        "account.list": None,
        "account.search": None,
        "account.add": None,
        "account.remove": None,
        "account.import": None,
        "account.export": None,
        "group": None,
        "group.list": None,
        "group.create": None,
        "group.delete": None,
        "group.add": None,
        "group.remove": None,
        "article.list": ArticleListInput,
        "article.content": ArticleContentInput,
        "task": None,
        "task.create": None,
        "task.list": None,
        "task.info": None,
        "task.run": None,
        "run": None,
        "run.list": None,
        "run.status": None,
        "run.export": None,
        "doctor": None,
    }
    output_model_map = {
        "auth.start": AuthStartOutput,
        "auth.confirm": AuthConfirmOutput,
        "auth.check": AuthCheckOutput,
        "account": None,
        "account.list": None,
        "account.search": None,
        "account.add": None,
        "account.remove": None,
        "account.import": None,
        "account.export": None,
        "group": None,
        "group.list": None,
        "group.create": None,
        "group.delete": None,
        "group.add": None,
        "group.remove": None,
        "article.list": ArticleListOutput,
        "article.content": ArticleContentOutput,
        "task": None,
        "task.create": None,
        "task.list": None,
        "task.info": None,
        "task.run": None,
        "run": None,
        "run.list": None,
        "run.status": None,
        "run.export": None,
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
        "auth.start": None,
        "auth.confirm": None,
        "auth.check": None,
        "account": None,
        "account.list": None,
        "account.search": None,
        "account.add": None,
        "account.remove": None,
        "account.import": None,
        "account.export": None,
        "group": None,
        "group.list": None,
        "group.create": None,
        "group.delete": None,
        "group.add": None,
        "group.remove": None,
        "article.list": ArticleListInput,
        "article.content": ArticleContentInput,
        "task": None,
        "task.create": None,
        "task.list": None,
        "task.info": None,
        "task.run": None,
        "run": None,
        "run.list": None,
        "run.status": None,
        "run.export": None,
        "doctor": None,
    }
    output_model_map = {
        "auth.start": AuthStartOutput,
        "auth.confirm": AuthConfirmOutput,
        "auth.check": AuthCheckOutput,
        "account": None,
        "account.list": None,
        "account.search": None,
        "account.add": None,
        "account.remove": None,
        "account.import": None,
        "account.export": None,
        "group": None,
        "group.list": None,
        "group.create": None,
        "group.delete": None,
        "group.add": None,
        "group.remove": None,
        "article.list": ArticleListOutput,
        "article.content": ArticleContentOutput,
        "task": None,
        "task.create": None,
        "task.list": None,
        "task.info": None,
        "task.run": None,
        "run": None,
        "run.list": None,
        "run.status": None,
        "run.export": None,
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
