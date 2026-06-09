"""任务执行引擎

两阶段执行：
  Phase 1: 文章列表获取（串行，公众号间隔 + 指数退避）
  Phase 2: 文章内容获取（并发，通过代理池）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from wechat_article_cli.api import WeChatClient
from wechat_article_cli.content import get_article_content
from wechat_article_cli.proxy import get_proxy_urls
from wechat_article_cli.storage import (
    Run,
    RunStatistics,
    save_run,
)

# 退避参数
_INITIAL_INTERVAL_FACTOR = 1.0
_MAX_INTERVAL_FACTOR = 4.0


async def run_task(run: Run) -> Run:
    """执行爬取任务（支持断点续跑）"""
    run.status = "running"
    run.updated_at = datetime.now(timezone.utc).isoformat()
    save_run(run)

    try:
        from wechat_article_cli.service import require_credentials

        creds = require_credentials()
    except ValueError as e:
        run.status = "failed"
        run.updated_at = datetime.now(timezone.utc).isoformat()
        save_run(run)
        raise ValueError(str(e)) from e

    # Phase 1: 文章列表获取
    logger.info("Phase 1/2：获取文章列表（{} 个公众号）", len(run.progress))
    async with WeChatClient(creds) as client:
        await _phase_list(run, client)

    # Phase 2: 文章内容获取
    if run.config.fetch_content:
        logger.info("Phase 2/2：获取文章内容（并发 {}）", run.config.content_concurrency)
        await _phase_content(run)
    else:
        logger.info("Phase 2/2：跳过内容获取（fetch_content=False）")

    # 汇总
    _update_statistics(run)
    has_failure = run.statistics.failed_accounts > 0 or run.statistics.content_failed > 0
    run.status = "failed" if has_failure else "completed"
    run.updated_at = datetime.now(timezone.utc).isoformat()
    save_run(run)

    return run


async def _phase_list(run: Run, client: WeChatClient) -> None:
    """Phase 1: 串行获取文章列表，公众号间有间隔 + 指数退避"""
    interval = run.config.account_interval
    factor = _INITIAL_INTERVAL_FACTOR

    for i, prog in enumerate(run.progress):
        if prog.status == "completed":
            logger.debug("跳过已完成：{}", prog.name)
            continue

        prog.status = "running"
        save_run(run)
        logger.info("[{}/{}] 获取文章列表：{}", i + 1, len(run.progress), prog.name)

        try:
            articles = await client.get_articles(
                prog.fakeid, count=run.config.article_count
            )

            # 日期过滤
            if run.config.after_date:
                articles = [
                    a for a in articles
                    if a.get("create_date", "") >= run.config.after_date
                ]

            prog.articles_found = len(articles)

            # 合并到 run.articles（去重）
            existing_links = {a["link"] for a in run.articles}
            for a in articles:
                if a["link"] not in existing_links:
                    a["account_name"] = prog.name
                    run.articles.append(a)
                    existing_links.add(a["link"])

            prog.status = "completed"
            factor = _INITIAL_INTERVAL_FACTOR
            logger.info("  → 获取 {} 篇文章", prog.articles_found)

        except Exception as e:
            prog.status = "failed"
            prog.error = str(e)
            factor = min(factor * 2, _MAX_INTERVAL_FACTOR)
            logger.error("  → 失败：{}（退避系数 {}）", e, factor)

        run.updated_at = datetime.now(timezone.utc).isoformat()
        save_run(run)

        if i < len(run.progress) - 1:
            wait = interval * factor
            logger.debug("等待 {:.1f} 秒...", wait)
            await asyncio.sleep(wait)


async def _phase_content(run: Run) -> None:
    """Phase 2: 并发获取文章内容"""
    from wechat_article_cli.content import is_article_cached
    from wechat_article_cli.proxy import ProxyManager

    proxy_urls = get_proxy_urls()
    # 共享 ProxyManager，代理统计和冷却在整个 Phase 2 内复用
    manager = ProxyManager(proxy_urls) if proxy_urls else None
    sem = asyncio.Semaphore(run.config.content_concurrency)

    _reset_content_progress(run)

    to_fetch = []
    for article in run.articles:
        if is_article_cached(article["link"]):
            _mark_cached(run, article)
        else:
            to_fetch.append(article)

    cached_count = len(run.articles) - len(to_fetch)
    logger.info(
        "共 {} 篇文章，{} 篇已缓存，{} 篇需获取",
        len(run.articles), cached_count, len(to_fetch),
    )

    if not to_fetch:
        return

    async def _fetch_one(article: dict) -> None:
        async with sem:
            title = article.get("title", "")[:20]
            try:
                await get_article_content(
                    article["link"], fmt="markdown", proxy_manager=manager
                )
                _mark_new(run, article)
                logger.debug("内容获取成功：{}", title)
            except Exception as e:
                error = _format_exception(e)
                _mark_content_failed(run, article, error)
                logger.warning("内容获取失败：{} - {}", title, error)

    await asyncio.gather(*[_fetch_one(a) for a in to_fetch])
    run.updated_at = datetime.now(timezone.utc).isoformat()
    save_run(run)


def _reset_content_progress(run: Run) -> None:
    for prog in run.progress:
        prog.articles_cached = 0
        prog.articles_new = 0
        prog.content_failed = 0


def _format_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return f"{type(exc).__name__}（无错误详情）"


def _mark_cached(run: Run, article: dict) -> None:
    article["content_status"] = "cached"
    article["content_error"] = ""
    name = article.get("account_name", "")
    prog = next((p for p in run.progress if p.name == name), None)
    if prog:
        prog.articles_cached += 1


def _mark_new(run: Run, article: dict) -> None:
    article["content_status"] = "fetched"
    article["content_error"] = ""
    name = article.get("account_name", "")
    prog = next((p for p in run.progress if p.name == name), None)
    if prog:
        prog.articles_new += 1


def _mark_content_failed(run: Run, article: dict, error: str) -> None:
    article["content_status"] = "failed"
    article["content_error"] = error
    name = article.get("account_name", "")
    prog = next((p for p in run.progress if p.name == name), None)
    if prog:
        prog.content_failed += 1


def _update_statistics(run: Run) -> None:
    run.statistics = RunStatistics(
        total_accounts=len(run.progress),
        completed_accounts=sum(1 for p in run.progress if p.status == "completed"),
        failed_accounts=sum(1 for p in run.progress if p.status == "failed"),
        total_articles=len(run.articles),
        new_articles=sum(p.articles_new for p in run.progress),
        cached_articles=sum(p.articles_cached for p in run.progress),
        content_failed=sum(p.content_failed for p in run.progress),
    )
