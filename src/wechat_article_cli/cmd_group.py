"""group 子命令

用法：
    wechat-article group list                           列出所有分组
    wechat-article group import <json路径>              从 JSON 批量导入分组
    wechat-article group export <json路径>              导出分组到 JSON
    wechat-article group create <分组名>                创建分组
    wechat-article group delete <分组名>                删除分组
    wechat-article group add <分组名> <名称>[,名称,...] 将公众号添加到分组
    wechat-article group remove <分组名> <名称>         从分组移除公众号

说明：
    被添加到分组的公众号必须已经在本地库中（通过 account add 添加）。
"""

from __future__ import annotations

import sys

from loguru import logger

from wechat_article_cli import service


def cmd_list() -> None:
    groups = service.list_groups()
    if not groups:
        logger.info("暂无分组")
        logger.info("创建分组: wechat-article group create <分组名>")
        return

    logger.info("共 {} 个分组：", len(groups))
    for g in groups:
        logger.info("")
        logger.info("分组：{}", g.name)
        logger.info("公众号数量：{}", len(g.accounts))
        if g.accounts:
            logger.info("成员：{}", "、".join(g.accounts))
    logger.info("")
    logger.info("添加成员: wechat-article group add <分组名> <名称>")
    logger.info("创建任务: wechat-article task create --group <分组名>")


def cmd_create(name: str) -> None:
    service.create_group(name)
    logger.info("已创建分组「{}」", name)
    logger.info("添加公众号到分组: wechat-article group add {} <名称>", name)


def cmd_import(json_path: str) -> None:
    result = service.import_groups_from_json(json_path)
    logger.info("批量导入分组完成：{}", json_path)
    logger.info("新增：{}", result["imported"])
    logger.info("更新：{}", result["updated"])
    logger.info("跳过：{}", result["skipped"])
    logger.info("无效分组：{}", result["invalid"])
    logger.info("无效成员：{}", result["invalid_accounts"])
    logger.info("当前分组总数：{}", result["total_groups"])


def cmd_export(json_path: str) -> None:
    result = service.export_groups_to_json(json_path)
    logger.info("已导出 {} 个分组到：{}", result["exported"], result["json_path"])


def cmd_delete(name: str) -> None:
    count = service.delete_group(name)
    logger.info("已删除分组「{}」（含 {} 个公众号）", name, count)


def cmd_add(group_name: str, names_str: str) -> None:
    names = [n.strip() for n in names_str.split(",") if n.strip()]
    result = service.add_to_group(group_name, names)

    if result["added"]:
        logger.info("已添加 {} 个公众号到分组「{}」：{}", len(result["added"]), group_name, "、".join(result["added"]))
    if result["skipped"]:
        logger.info("已跳过 {} 个（已在分组中）：{}", len(result["skipped"]), "、".join(result["skipped"]))
    if result["not_in_lib"]:
        logger.error("未添加 {} 个（不在本地库中）：{}", len(result["not_in_lib"]), "、".join(result["not_in_lib"]))
        logger.info("请先 wechat-article account add <名称> 添加到本地库")


def cmd_remove_account(group_name: str, name: str) -> None:
    service.remove_from_group(group_name, name)
    logger.info("已从分组「{}」中移除「{}」", group_name, name)


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list":
            cmd_list()
        elif cmd == "import":
            if not rest:
                logger.error("用法: wechat-article group import <json路径>")
                sys.exit(1)
            cmd_import(rest[0])
        elif cmd == "export":
            if not rest:
                logger.error("用法: wechat-article group export <json路径>")
                sys.exit(1)
            cmd_export(rest[0])
        elif cmd == "create":
            if not rest:
                logger.error("用法: wechat-article group create <分组名>")
                sys.exit(1)
            cmd_create(rest[0])
        elif cmd == "delete":
            if not rest:
                logger.error("用法: wechat-article group delete <分组名>")
                sys.exit(1)
            cmd_delete(rest[0])
        elif cmd == "add":
            if len(rest) < 2:
                logger.error("用法: wechat-article group add <分组名> <名称>[,名称,...]")
                sys.exit(1)
            cmd_add(rest[0], rest[1])
        elif cmd == "remove":
            if len(rest) < 2:
                logger.error("用法: wechat-article group remove <分组名> <名称>")
                sys.exit(1)
            cmd_remove_account(rest[0], rest[1])
        else:
            logger.error("未知命令: group {}，可选: list, import, export, create, delete, add, remove", cmd)
            sys.exit(1)
    except ValueError as e:
        logger.error("{}", e)
        sys.exit(1)
