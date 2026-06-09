"""微信公众号业务逻辑

纯业务逻辑层，不做 CLI 输出，不调用 sys.exit。
返回数据结构，由 cmd_* 层负责格式化展示。
异常表示业务错误，由 cmd_* 层捕获并输出友好信息。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from wechat_article_cli.storage import Run, TaskDefinition

from wechat_article_cli.api import WeChatClient
from wechat_article_cli.storage import (
    AccountGroup,
    Credentials,
    SavedAccount,
    find_account_by_name,
    is_credentials_valid,
    load_credentials,
    load_groups,
    load_saved_accounts,
    load_search_cache,
    save_groups,
    save_saved_accounts,
    save_search_cache,
)

# --- 凭证 ---


def require_credentials() -> Credentials:
    """检查并返回有效凭证，无效则抛异常"""
    creds = load_credentials()
    if not creds:
        raise ValueError("未登录。请执行 wechat-article auth start 生成二维码，需要用户使用微信扫码登录")
    if not is_credentials_valid(creds):
        raise ValueError("凭证已过期。请执行 wechat-article auth start 重新生成二维码，需要用户使用微信扫码登录")
    return creds


async def start_auth() -> str:
    """发起登录，生成二维码，返回二维码文件路径"""
    from wechat_article_cli.storage import (
        LoginSession,
        get_qrcode_path,
        save_login_session,
    )

    async with WeChatClient() as client:
        uuid_cookie = await client.start_login()
        qrcode_data = await client.get_qrcode(uuid_cookie)

    qrcode_path = get_qrcode_path()
    qrcode_path.write_bytes(qrcode_data)
    save_login_session(
        LoginSession(
            uuid_cookie=uuid_cookie,
            created_at=datetime.now(timezone.utc).isoformat(),
            qrcode_path=str(qrcode_path),
        )
    )
    return str(qrcode_path)


async def confirm_auth() -> dict:
    """检查扫码状态，确认则保存凭证。返回 {status, ...} 字典"""
    from wechat_article_cli.api import (
        SCAN_CONFIRMED,
        SCAN_EXPIRED_1,
        SCAN_EXPIRED_2,
        SCAN_NO_EMAIL,
        SCAN_SCANNED,
        SCAN_SCANNED_2,
        SCAN_WAITING,
    )
    from wechat_article_cli.storage import (
        clear_login_session,
        load_login_session,
        save_credentials,
    )

    session = load_login_session()
    if not session:
        raise ValueError("没有进行中的登录会话。请先执行 wechat-article auth start 生成二维码")

    async with WeChatClient() as client:
        status_data = await client.check_scan_status(session.uuid_cookie)
        status = status_data["status"]

        if status == SCAN_WAITING:
            return {"status": "waiting", "qrcode_path": session.qrcode_path}
        elif status in (SCAN_SCANNED, SCAN_SCANNED_2):
            return {"status": "scanned"}
        elif status == SCAN_CONFIRMED:
            creds = await client.execute_login(session.uuid_cookie)
            save_credentials(creds)
            clear_login_session()
            return {"status": "confirmed", "expires_at": creds.expires_at}
        elif status in (SCAN_EXPIRED_1, SCAN_EXPIRED_2):
            clear_login_session()
            return {"status": "expired"}
        elif status == SCAN_NO_EMAIL:
            clear_login_session()
            return {"status": "no_email"}
        else:
            return {"status": "unknown", "raw_status": status}


def check_auth() -> dict:
    """检查凭证状态，返回 {status, ...} 字典"""
    creds = load_credentials()
    if not creds:
        return {"status": "not_logged_in"}
    if not is_credentials_valid(creds):
        return {"status": "expired", "expires_at": creds.expires_at}
    remaining = (
        datetime.fromisoformat(creds.expires_at) - datetime.now(timezone.utc)
    )
    return {
        "status": "valid",
        "created_at": creds.created_at,
        "expires_at": creds.expires_at,
        "remaining_seconds": int(remaining.total_seconds()),
    }


# --- 公众号管理 ---


async def search_accounts(query: str) -> list[dict]:
    """搜索公众号，缓存结果"""
    creds = require_credentials()
    async with WeChatClient(creds) as client:
        results = await client.search_accounts(query)
    save_search_cache(results)
    return results


def add_accounts(names: list[str]) -> dict:
    """从搜索缓存添加公众号。返回 {added, skipped, not_found}"""
    cache = load_search_cache()
    saved = load_saved_accounts()
    existing_names = {acc.name for acc in saved.accounts}

    added, skipped, not_found = [], [], []

    for name in names:
        if name in existing_names:
            skipped.append(name)
            continue
        match = next((r for r in cache if r["name"] == name), None)
        if not match:
            not_found.append(name)
            continue
        saved.accounts.append(SavedAccount(
            fakeid=match["fakeid"],
            name=match["name"],
            avatar=match.get("avatar"),
            signature=match.get("signature"),
            added_at=datetime.now(timezone.utc).isoformat(),
        ))
        existing_names.add(name)
        added.append(name)

    if added:
        save_saved_accounts(saved)

    return {"added": added, "skipped": skipped, "not_found": not_found}


def import_accounts_from_json(json_path: str) -> dict:
    """从 JSON 文件批量导入公众号。返回 {imported, updated, skipped, invalid}。"""
    path = Path(json_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"JSON 文件不存在：{path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：{exc}") from exc

    if isinstance(raw, dict) and isinstance(raw.get("accounts"), list):
        raw = raw["accounts"]
    if not isinstance(raw, list):
        raise ValueError("导入文件必须是公众号数组 JSON，或对象中包含 accounts 数组")

    saved = load_saved_accounts()
    imported = 0
    updated = 0
    skipped = 0
    invalid = 0

    by_name = {acc.name: acc for acc in saved.accounts}
    by_fakeid = {acc.fakeid: acc for acc in saved.accounts}

    for item in raw:
        if not isinstance(item, dict):
            invalid += 1
            continue

        fakeid = str(item.get("fakeid", "")).strip()
        name = str(item.get("name", "")).strip()
        if not fakeid or not name:
            invalid += 1
            continue

        avatar = item.get("avatar")
        signature = item.get("signature")
        added_at = item.get("added_at")

        existing = by_fakeid.get(fakeid) or by_name.get(name)
        if existing is None:
            created = SavedAccount(
                fakeid=fakeid,
                name=name,
                avatar=avatar,
                signature=signature,
                added_at=str(added_at or datetime.now(timezone.utc).isoformat()),
            )
            saved.accounts.append(created)
            by_name[created.name] = created
            by_fakeid[created.fakeid] = created
            imported += 1
            continue

        changed = False
        if existing.fakeid != fakeid:
            old_fakeid = existing.fakeid
            existing.fakeid = fakeid
            by_fakeid.pop(old_fakeid, None)
            by_fakeid[fakeid] = existing
            changed = True
        if existing.name != name:
            old_name = existing.name
            existing.name = name
            by_name.pop(old_name, None)
            by_name[name] = existing
            changed = True
        if existing.avatar != avatar:
            existing.avatar = avatar
            changed = True
        if existing.signature != signature:
            existing.signature = signature
            changed = True

        if changed:
            updated += 1
        else:
            skipped += 1

    if imported or updated:
        save_saved_accounts(saved)

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "invalid": invalid,
    }


def export_accounts_to_json(json_path: str) -> dict:
    """把本地库中的公众号导出为 JSON 数组。"""
    path = Path(json_path).expanduser().resolve()
    saved = load_saved_accounts()
    payload = [
        {
            "fakeid": account.fakeid,
            "name": account.name,
            "avatar": account.avatar,
            "signature": account.signature,
        }
        for account in saved.accounts
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "exported": len(payload),
        "json_path": str(path),
    }


def remove_account(name: str) -> None:
    """删除公众号（同时从所有分组移除）"""
    saved = load_saved_accounts()
    idx = next((i for i, a in enumerate(saved.accounts) if a.name == name), None)
    if idx is None:
        raise ValueError(f"公众号「{name}」不在本地库中")

    saved.accounts.pop(idx)
    save_saved_accounts(saved)

    # 联动清理分组
    groups = load_groups()
    for g in groups.groups:
        if name in g.accounts:
            g.accounts.remove(name)
    save_groups(groups)


def list_accounts(group_name: Optional[str] = None) -> list[SavedAccount]:
    """列出账号，可按分组筛选"""
    saved = load_saved_accounts()
    if not group_name:
        return saved.accounts

    groups = load_groups()
    group = next((g for g in groups.groups if g.name == group_name), None)
    if not group:
        raise ValueError(f"分组「{group_name}」不存在")
    return [a for a in saved.accounts if a.name in group.accounts]


# --- 分组管理 ---


def create_group(name: str) -> None:
    groups = load_groups()
    if any(g.name == name for g in groups.groups):
        raise ValueError(f"分组「{name}」已存在")
    groups.groups.append(AccountGroup(name=name))
    save_groups(groups)


def delete_group(name: str) -> int:
    """删除分组，返回被移除的公众号数量"""
    groups = load_groups()
    idx = next((i for i, g in enumerate(groups.groups) if g.name == name), None)
    if idx is None:
        raise ValueError(f"分组「{name}」不存在")
    removed = groups.groups.pop(idx)
    save_groups(groups)
    return len(removed.accounts)


def add_to_group(group_name: str, names: list[str]) -> dict:
    """添加公众号到分组。返回 {added, skipped, not_in_lib}"""
    groups = load_groups()
    group = next((g for g in groups.groups if g.name == group_name), None)
    if not group:
        raise ValueError(f"分组「{group_name}」不存在，请先 wechat-article group create {group_name}")

    added, skipped, not_in_lib = [], [], []
    for name in names:
        if name in group.accounts:
            skipped.append(name)
        elif not find_account_by_name(name):
            not_in_lib.append(name)
        else:
            group.accounts.append(name)
            added.append(name)

    if added:
        save_groups(groups)
    return {"added": added, "skipped": skipped, "not_in_lib": not_in_lib}


def remove_from_group(group_name: str, name: str) -> None:
    groups = load_groups()
    group = next((g for g in groups.groups if g.name == group_name), None)
    if not group:
        raise ValueError(f"分组「{group_name}」不存在")
    if name not in group.accounts:
        raise ValueError(f"公众号「{name}」不在分组「{group_name}」中")
    group.accounts.remove(name)
    save_groups(groups)


def list_groups() -> list[AccountGroup]:
    return load_groups().groups


# --- 文章获取 ---


async def list_articles(
    name: Optional[str] = None,
    group_name: Optional[str] = None,
    count: int = 5,
    offset: int = 0,
) -> list[tuple[str, list[dict]]]:
    """获取文章列表，返回 [(account_name, articles), ...]"""
    targets = _resolve_targets([name] if name else None, group_name)

    creds = require_credentials()
    results = []
    async with WeChatClient(creds) as client:
        for acc_name, fakeid in targets:
            articles = await client.get_articles(fakeid, count=count, offset=offset)
            results.append((acc_name, articles))
    return results


async def get_content(
    link: str, fmt: str = "markdown"
) -> dict:
    """获取文章内容（自动缓存），返回结果字典"""
    from wechat_article_cli.content import get_article_content
    from wechat_article_cli.proxy import get_proxy_urls

    fmt_map = {"md": "markdown", "markdown": "markdown", "html": "html", "text": "text"}
    real_fmt = fmt_map.get(fmt)
    if not real_fmt:
        raise ValueError(f"不支持的格式: {fmt}，可选: md, html, text")

    proxy_urls = get_proxy_urls()
    return await get_article_content(link, fmt=real_fmt, proxy_urls=proxy_urls)


# --- 任务管理 ---


def _resolve_targets(
    accounts: list[str] | None, group_name: str | None
) -> list[tuple[str, str]]:
    """解析目标公众号，返回 [(name, fakeid)]"""
    targets: list[tuple[str, str]] = []

    if group_name:
        groups = load_groups()
        group = next((g for g in groups.groups if g.name == group_name), None)
        if not group:
            raise ValueError(f"分组「{group_name}」不存在")
        for acc_name in group.accounts:
            acc = find_account_by_name(acc_name)
            if acc:
                targets.append((acc.name, acc.fakeid))
    elif accounts:
        for name in accounts:
            acc = find_account_by_name(name)
            if not acc:
                raise ValueError(f"公众号「{name}」不在本地库中")
            targets.append((acc.name, acc.fakeid))
    else:
        raise ValueError("请指定公众号名称或分组")

    if not targets:
        raise ValueError("没有找到任何目标公众号")
    return targets


def create_task(
    name: str = "",
    accounts: list[str] | None = None,
    group_name: str | None = None,
    article_count: int = 5,
    account_interval: float = 10.0,
    after_date: str | None = None,
    fetch_content: bool = True,
    content_concurrency: int = 3,
) -> TaskDefinition:
    """创建任务定义（可复用模板）"""
    import uuid

    from wechat_article_cli.storage import (
        TaskConfig,
        TaskDefinition,
        load_all_tasks,
        save_all_tasks,
    )

    targets = _resolve_targets(accounts, group_name)

    config = TaskConfig(
        accounts=[t[0] for t in targets],
        group=group_name,
        article_count=article_count,
        account_interval=account_interval,
        after_date=after_date,
        fetch_content=fetch_content,
        content_concurrency=content_concurrency,
    )

    task = TaskDefinition(
        task_id=uuid.uuid4().hex[:8],
        name=name or (group_name or ",".join(config.accounts[:3])),
        created_at=datetime.now(timezone.utc).isoformat(),
        config=config,
    )

    tasks = load_all_tasks()
    tasks.append(task)
    save_all_tasks(tasks)
    return task


def get_task(task_id: str) -> TaskDefinition:
    from wechat_article_cli.storage import find_task

    task = find_task(task_id)
    if not task:
        raise ValueError(f"任务 {task_id} 不存在")
    return task


def get_all_tasks() -> list[TaskDefinition]:
    from wechat_article_cli.storage import load_all_tasks

    return load_all_tasks()


def start_run(task_id: str) -> Run:
    """为指定任务创建一个新的 Run"""
    import uuid

    from wechat_article_cli.storage import AccountProgress, Run, save_run

    task = get_task(task_id)
    targets = _resolve_targets(task.config.accounts, None)

    now = datetime.now(timezone.utc).isoformat()
    run = Run(
        run_id=uuid.uuid4().hex[:8],
        task_id=task_id,
        created_at=now,
        updated_at=now,
        config=task.config,
        progress=[
            AccountProgress(name=name, fakeid=fakeid)
            for name, fakeid in targets
        ],
    )

    save_run(run)
    return run


def get_run(run_id: str) -> Run:
    from wechat_article_cli.storage import load_run

    run = load_run(run_id)
    if not run:
        raise ValueError(f"执行记录 {run_id} 不存在")
    return run


def get_all_runs() -> list[Run]:
    from wechat_article_cli.storage import list_run_ids, load_run

    runs = []
    for rid in list_run_ids():
        r = load_run(rid)
        if r:
            runs.append(r)
    return runs
