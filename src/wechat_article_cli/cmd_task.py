"""task 子命令 — 任务定义管理

用法：
    wechat-article task create --group <分组> [--name <名称>] [--count N] [--interval N]
    wechat-article task list
    wechat-article task info <task_id>
    wechat-article task run <task_id>
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger


def cmd_create(args: list[str]) -> None:
    from wechat_article_cli.service import create_task

    group = None
    accounts: list[str] = []
    name = ""
    count = 5
    interval = 10.0
    after_date = None
    fetch_content = True
    concurrency = 3

    i = 0
    try:
        while i < len(args):
            if args[i] == "--group" and i + 1 < len(args):
                group = args[i + 1]
                i += 2
            elif args[i] == "--accounts" and i + 1 < len(args):
                accounts = [a.strip() for a in args[i + 1].split(",")]
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
                logger.error("未知参数: {}", args[i])
                sys.exit(1)

        task = create_task(
            name=name,
            accounts=accounts or None,
            group_name=group,
            article_count=count,
            account_interval=interval,
            after_date=after_date,
            fetch_content=fetch_content,
            content_concurrency=concurrency,
        )
    except (ValueError, TypeError) as e:
        logger.error("参数错误：{}", e)
        sys.exit(1)

    logger.info("任务已创建")
    logger.info("任务ID：{}", task.task_id)
    logger.info("名称：{}", task.name)
    logger.info("目标：{} 个公众号", len(task.config.accounts))
    logger.info("配置：每号 {} 篇，间隔 {}s", count, interval)
    logger.info("执行: wechat-article task run {}", task.task_id)


def cmd_list(args: list[str]) -> None:
    from wechat_article_cli.service import get_all_tasks

    tasks = get_all_tasks()
    if not tasks:
        logger.info("暂无任务")
        logger.info("创建任务: wechat-article task create --group <分组> --name <名称>")
        return

    logger.info("共 {} 个任务：", len(tasks))
    for t in tasks:
        accts = len(t.config.accounts)
        logger.info("  {}  {}  ({} 个公众号)  创建={}", t.task_id, t.name, accts, t.created_at[:10])
    logger.info("查看详情: wechat-article task info <task_id>")
    logger.info("执行任务: wechat-article task run <task_id>")


def cmd_info(args: list[str]) -> None:
    if not args:
        logger.error("请指定任务ID: wechat-article task info <task_id>")
        sys.exit(1)

    from wechat_article_cli.service import get_task

    try:
        task = get_task(args[0])
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)

    logger.info("任务ID：{}", task.task_id)
    logger.info("名称：{}", task.name)
    logger.info("创建时间：{}", task.created_at[:19])
    c = task.config
    logger.info("公众号：{}", ", ".join(c.accounts))
    logger.info(
        "配置：每号 {} 篇，间隔 {}s，并发 {}",
        c.article_count,
        c.account_interval,
        c.content_concurrency,
    )
    if c.after_date:
        logger.info("日期过滤：{} 之后", c.after_date)
    logger.info("执行此任务: wechat-article task run {}", task.task_id)


def cmd_run(args: list[str]) -> None:
    if not args:
        logger.error("请指定任务ID: wechat-article task run <task_id>")
        sys.exit(1)

    from wechat_article_cli.service import start_run
    from wechat_article_cli.task_runner import run_task

    try:
        run = start_run(args[0])
        logger.info("创建执行记录：{}", run.run_id)
        run = asyncio.run(run_task(run))
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)

    logger.info("执行完成")
    s = run.statistics
    logger.info(
        "统计：公众号 {}/{} 完成，{} 失败",
        s.completed_accounts,
        s.total_accounts,
        s.failed_accounts,
    )
    logger.info(
        "文章：共 {} 篇，新增 {}，缓存 {}，内容失败 {}",
        s.total_articles,
        s.new_articles,
        s.cached_articles,
        s.content_failed,
    )
    logger.info("查看详情: wechat-article run status {}", run.run_id)


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    rest = args[1:]

    cmds = {"create": cmd_create, "list": cmd_list, "info": cmd_info, "run": cmd_run}
    if cmd in cmds:
        cmds[cmd](rest)
    else:
        logger.error("未知命令: task {}，可选: create, list, info, run", cmd)
        sys.exit(1)
