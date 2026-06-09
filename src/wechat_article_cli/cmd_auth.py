"""auth 子命令

用法：
    wechat-article auth start       生成登录二维码
    wechat-article auth confirm     扫码后确认登录
    wechat-article auth check       检查凭证状态
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from loguru import logger

from wechat_article_cli.storage import CN_TZ


def cmd_start() -> None:
    from wechat_article_cli.service import start_auth

    try:
        qrcode_path = asyncio.run(start_auth())
    except (ValueError, RuntimeError, OSError) as e:
        logger.error("启动登录失败：{}", e)
        sys.exit(1)

    logger.info("二维码已生成")
    logger.info("二维码路径：{}", qrcode_path)
    logger.info("请将二维码展示给用户，让用户使用微信扫描登录")
    logger.info("二维码有效期约 5 分钟")
    logger.info("用户扫码确认后，请执行: wechat-article auth confirm")


def cmd_confirm() -> None:
    from wechat_article_cli.service import confirm_auth

    try:
        result = asyncio.run(confirm_auth())
    except (ValueError, RuntimeError, OSError) as e:
        logger.error("确认登录失败：{}", e)
        sys.exit(1)

    status = result["status"]
    if status == "waiting":
        logger.info("状态：等待扫码")
        logger.info("用户尚未扫描二维码，请提醒用户扫码")
        logger.info("二维码路径：{}", result.get("qrcode_path", ""))
    elif status == "scanned":
        logger.info("状态：已扫码，等待确认")
        logger.info("用户已扫码但未点确认，请提醒用户在微信上点击确认")
        logger.info("确认后再次执行: wechat-article auth confirm")
    elif status == "confirmed":
        expires = datetime.fromisoformat(result["expires_at"])
        expires_local = expires.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M")
        logger.info("登录成功")
        logger.info("凭证已保存，有效期至 {}", expires_local)
    elif status == "expired":
        logger.error("二维码已过期")
        logger.info("请执行 wechat-article auth start 重新生成二维码，需要用户微信扫码")
        sys.exit(1)
    elif status == "no_email":
        logger.error("该微信账号未绑定邮箱，无法登录公众号后台")
        sys.exit(1)
    else:
        logger.warning("未知扫码状态: {}", result.get("raw_status", status))


def cmd_check() -> None:
    from wechat_article_cli.service import check_auth

    result = check_auth()
    status = result["status"]

    if status == "not_logged_in":
        logger.info("状态：未登录")
        logger.info("请执行 wechat-article auth start 生成二维码，需要用户微信扫码登录")
    elif status == "expired":
        expires = datetime.fromisoformat(result["expires_at"])
        expires_local = expires.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M")
        logger.info("状态：凭证已过期")
        logger.info("过期时间：{}", expires_local)
        logger.info("请执行 wechat-article auth start 重新生成二维码，需要用户微信扫码")
    elif status == "valid":
        created = datetime.fromisoformat(result["created_at"])
        expires = datetime.fromisoformat(result["expires_at"])
        secs = result["remaining_seconds"]
        hours, minutes = secs // 3600, (secs % 3600) // 60
        logger.info("状态：凭证有效")
        logger.info("登录时间：{}", created.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M"))
        logger.info("过期时间：{}", expires.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M"))
        logger.info("剩余有效期：{}小时{}分钟", hours, minutes)
        logger.info("可用操作: wechat-article account search / wechat-article task list / wechat-article task run")


def dispatch(args: list[str]) -> None:
    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)
    cmd = args[0]
    cmds = {"start": cmd_start, "confirm": cmd_confirm, "check": cmd_check}
    if cmd in cmds:
        cmds[cmd]()
    else:
        logger.error("未知命令: auth {}，可选: start, confirm, check", cmd)
        sys.exit(1)
