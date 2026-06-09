"""article 子命令

用法：
    wechat-article article list <公众号名称>                获取指定公众号的文章列表
    wechat-article article list --group <分组名>            获取分组内所有公众号的文章
    wechat-article article content <文章链接>               获取文章内容（默认 markdown）

参数：
    --count N              获取数量，默认 5，最大 20
    --offset N             分页偏移，默认 0
    --format md|html|text  文章内容格式，默认 markdown
    --output <路径>        指定输出文件路径
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import sys
from pathlib import Path

from loguru import logger

from wechat_article_cli import service
from wechat_article_cli._toolkit.runtime.home import get_data_dir


def _print_articles(articles: list[dict], account_name: str) -> None:
    """统一的文章列表输出"""
    if not articles:
        logger.info("公众号「{}」暂无文章", account_name)
        return

    logger.info("公众号「{}」共 {} 篇文章：", account_name, len(articles))
    for a in articles:
        logger.info("")
        logger.info("标题：{}", a["title"])
        logger.info("日期：{}", a["create_date"])
        logger.info("链接：{}", a["link"])
        if a.get("author"):
            logger.info("作者：{}", a["author"])
        if a.get("digest"):
            logger.info("摘要：{}", a["digest"])


def _safe_filename(title: str, link: str, ext: str) -> str:
    """生成跨平台安全的文件名：标题前20字_hash8.ext"""
    safe = re.sub(r"[^\u4e00-\u9fff\w\-]", "", title)[:20]
    safe = safe.strip("._- ") or "article"
    link_hash = hashlib.md5(link.encode()).hexdigest()[:8]
    return f"{safe}_{link_hash}{ext}"


def cmd_list(name: str | None, group_name: str | None, count: int, offset: int) -> None:
    results = asyncio.run(service.list_articles(name=name, group_name=group_name, count=count, offset=offset))
    for acc_name, articles in results:
        _print_articles(articles, acc_name)
        if len(results) > 1:
            logger.info("")
    total = sum(len(arts) for _, arts in results)
    if total > 0:
        logger.info("获取文章内容: wechat-article article content <链接> [--format md|html|text]")


def cmd_content(link: str, fmt: str, output: str | None) -> None:
    result = asyncio.run(service.get_content(link, fmt=fmt))

    if output:
        out_path = Path(output)
    else:
        real_fmt = result["format"]
        ext = {"markdown": ".md", "html": ".html", "text": ".txt"}[real_fmt]
        export_dir = get_data_dir("wechat_article") / "exports" / "articles"
        export_dir.mkdir(parents=True, exist_ok=True)
        out_path = export_dir / _safe_filename(result["title"], link, ext)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result["content"], encoding="utf-8")

    source = "缓存" if result.get("cached") else "网络"
    logger.info("文章获取成功（来源：{}）", source)
    logger.info("标题：{}", result["title"])
    if result.get("author"):
        logger.info("作者：{}", result["author"])
    if result.get("publish_date"):
        logger.info("日期：{}", result["publish_date"])
    logger.info("格式：{}", result["format"])
    logger.info("输出路径：{}", out_path.resolve())
    logger.info("内容长度：{} 字符", len(result["content"]))


def _parse_kv(args: list[str], key: str, default: str | None = None) -> str | None:
    if key in args:
        idx = args.index(key)
        if idx + 1 < len(args):
            return args[idx + 1]
    return default


def _extract_positional(args: list[str]) -> list[str]:
    """提取参数列表中的位置参数（跳过 --key value 对）"""
    result = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a.startswith("--"):
            skip = True
            continue
        result.append(a)
    return result


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list":
            group_name = _parse_kv(rest, "--group")
            count = int(_parse_kv(rest, "--count", "5"))
            offset = int(_parse_kv(rest, "--offset", "0"))
            name = _extract_positional(rest)[0] if not group_name and _extract_positional(rest) else None

            if not name and not group_name:
                logger.error("用法: wechat-article article list <名称> 或 --group <分组>")
                sys.exit(1)
            cmd_list(name, group_name, count, offset)

        elif cmd == "content":
            positional = _extract_positional(rest)
            if not positional:
                logger.error("用法: wechat-article article content <链接> [--format md|html|text]")
                sys.exit(1)
            link = positional[0]
            fmt = _parse_kv(rest, "--format", "md")
            output = _parse_kv(rest, "--output")
            cmd_content(link, fmt, output)

        else:
            logger.error("未知命令: article {}，可选: list, content", cmd)
            sys.exit(1)
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)
