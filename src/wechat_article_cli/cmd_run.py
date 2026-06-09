"""run 子命令 — 执行记录管理

用法：
    wechat-article run list
    wechat-article run status <run_id>
    wechat-article run export <run_id> [--format json|csv|excel]
"""

from __future__ import annotations

import sys

from loguru import logger


def cmd_list(args: list[str]) -> None:
    from wechat_article_cli.service import get_all_runs

    runs = get_all_runs()
    if not runs:
        logger.info("暂无执行记录")
        logger.info("创建执行: wechat-article task run <task_id>")
        return

    logger.info("共 {} 条执行记录：", len(runs))
    for r in runs:
        s = r.statistics
        logger.info(
            "  {}  [{}]  task={}  文章={}  创建={}",
            r.run_id, r.status, r.task_id, s.total_articles, r.created_at[:10],
        )
    logger.info("查看详情: wechat-article run status <run_id>")
    logger.info("导出结果: wechat-article run export <run_id> --format json|csv|excel")


def cmd_status(args: list[str]) -> None:
    if not args:
        logger.error("请指定 run_id: wechat-article run status <run_id>")
        sys.exit(1)

    from wechat_article_cli.service import get_run

    try:
        run = get_run(args[0])
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)

    logger.info("Run：{}", run.run_id)
    logger.info("Task：{}", run.task_id)
    logger.info("状态：{}", run.status)
    logger.info("创建时间：{}", run.created_at[:19])
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
    for p in run.progress:
        icon = {"completed": "✓", "failed": "✗", "running": "⟳"}.get(p.status, "○")
        extra = f"（{p.error}）" if p.error else ""
        fail_info = f" 内容失败={p.content_failed}" if p.content_failed else ""
        logger.info(
            "  {} {}: 找到={} 新增={} 缓存={}{}{}",
            icon, p.name, p.articles_found, p.articles_new, p.articles_cached, fail_info, extra,
        )
    failed_articles = [
        a for a in run.articles if a.get("content_status") == "failed"
    ]
    if failed_articles:
        logger.info("正文失败明细：")
        for article in failed_articles[:10]:
            logger.info(
                "  - {}：{}",
                article.get("title", ""),
                article.get("content_error", "无错误详情"),
            )
    logger.info("导出结果: wechat-article run export {} --format json|csv|excel", run.run_id)


def cmd_export(args: list[str]) -> None:
    if not args:
        logger.error("用法: wechat-article run export <run_id> [--format json|csv|excel]")
        sys.exit(1)

    from wechat_article_cli.export import export_run
    from wechat_article_cli.service import get_run

    run_id = args[0]
    fmt = "json"
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1]

    try:
        run = get_run(run_id)
        path = export_run(run, fmt=fmt)
    except (ValueError, RuntimeError) as e:
        logger.error("{}", e)
        sys.exit(1)

    logger.info("导出成功")
    logger.info("格式：{}", fmt)
    logger.info("路径：{}", path)
    logger.info("文章数：{}", len(run.articles))


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    cmd = args[0]
    rest = args[1:]

    cmds = {"list": cmd_list, "status": cmd_status, "export": cmd_export}
    if cmd in cmds:
        cmds[cmd](rest)
    else:
        logger.error("未知命令: run {}，可选: list, status, export", cmd)
        sys.exit(1)
