"""account 子命令

用法：
    wechat-article account search <关键词>              搜索公众号
    wechat-article account add <名称>[,名称,...]        添加公众号到本地库
    wechat-article account remove <名称>                从本地库删除
    wechat-article account list [--group <分组>]        列出已保存的公众号
    wechat-article account import <json路径>            从 JSON 批量导入公众号
    wechat-article account export <json路径>            导出本地库到 JSON
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from wechat_article_cli import service


def cmd_search(query: str) -> None:
    results = asyncio.run(service.search_accounts(query))

    if not results:
        logger.info("未找到匹配「{}」的公众号", query)
        return

    logger.info("搜索「{}」找到 {} 个公众号：", query, len(results))
    for acc in results:
        logger.info("")
        logger.info("名称：{}", acc["name"])
        logger.info("fakeid：{}", acc["fakeid"])
        if acc.get("signature"):
            logger.info("简介：{}", acc["signature"])
        if acc.get("avatar"):
            logger.info("头像：{}", acc["avatar"])
    logger.info("")
    logger.info("可使用 wechat-article account add <名称> 将公众号添加到本地库")


def cmd_add(names_str: str) -> None:
    names = [n.strip() for n in names_str.split(",") if n.strip()]
    if not names:
        logger.error("请指定公众号名称")
        sys.exit(1)

    result = service.add_accounts(names)

    if result["added"]:
        logger.info("已添加 {} 个公众号：{}", len(result["added"]), "、".join(result["added"]))
    if result["skipped"]:
        logger.info("已跳过 {} 个（已存在）：{}", len(result["skipped"]), "、".join(result["skipped"]))
    if result["not_found"]:
        logger.error("未找到 {} 个公众号：{}", len(result["not_found"]), "、".join(result["not_found"]))
        logger.info("请先执行 wechat-article account search <关键词> 搜索")
    if result["added"]:
        logger.info("将公众号加入分组: wechat-article group add <分组名> <名称>")
        logger.info("获取文章: wechat-article article list <名称>")


def cmd_remove(name: str) -> None:
    service.remove_account(name)
    logger.info("已删除公众号「{}」（同时从所有分组中移除）", name)


def cmd_list(group_name: str | None) -> None:
    accounts = service.list_accounts(group_name)
    label = f"分组「{group_name}」中有" if group_name else "本地库共"
    logger.info("{} {} 个公众号：", label, len(accounts))

    if not accounts:
        logger.info("（空）")
        logger.info("添加公众号: wechat-article account add <名称>")
        return
    for acc in accounts:
        logger.info("")
        logger.info("名称：{}", acc.name)
        logger.info("fakeid：{}", acc.fakeid)
        if acc.signature:
            logger.info("简介：{}", acc.signature)


def cmd_import(json_path: str) -> None:
    result = service.import_accounts_from_json(json_path)
    logger.info("批量导入完成：{}", json_path)
    logger.info("新增：{}", result["imported"])
    logger.info("更新：{}", result["updated"])
    logger.info("跳过：{}", result["skipped"])
    logger.info("无效：{}", result["invalid"])


def cmd_export(json_path: str) -> None:
    result = service.export_accounts_to_json(json_path)
    logger.info("已导出 {} 个公众号到：{}", result["exported"], result["json_path"])


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    cmd, rest = args[0], args[1:]
    try:
        if cmd == "search":
            if not rest:
                logger.error("用法: wechat-article account search <关键词>")
                sys.exit(1)
            cmd_search(rest[0])
        elif cmd == "add":
            if not rest:
                logger.error("用法: wechat-article account add <名称>[,名称,...]")
                sys.exit(1)
            cmd_add(rest[0])
        elif cmd == "remove":
            if not rest:
                logger.error("用法: wechat-article account remove <名称>")
                sys.exit(1)
            cmd_remove(rest[0])
        elif cmd == "list":
            group_name = None
            if "--group" in rest:
                idx = rest.index("--group")
                if idx + 1 < len(rest):
                    group_name = rest[idx + 1]
            cmd_list(group_name)
        elif cmd == "import":
            if not rest:
                logger.error("用法: wechat-article account import <json路径>")
                sys.exit(1)
            cmd_import(rest[0])
        elif cmd == "export":
            if not rest:
                logger.error("用法: wechat-article account export <json路径>")
                sys.exit(1)
            cmd_export(rest[0])
        else:
            logger.error("未知命令: account {}，可选: search, add, remove, list, import, export", cmd)
            sys.exit(1)
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)
