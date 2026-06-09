"""凭证和数据存储管理

登录凭证（token + cookies）和收藏公众号列表的持久化。
默认存储在 wechat-article capability home 下。
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field, field_validator

from wechat_article_cli._toolkit.runtime.home import get_data_dir

# 中国时区（共享常量）
CN_TZ = timezone(timedelta(hours=8))


class Credentials(BaseModel):
    """登录凭证"""

    auth_key: str
    token: str
    cookies: dict[str, str]
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    created_at: str  # ISO 8601
    expires_at: str  # ISO 8601

    @field_validator("token", "auth_key")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v


class LoginSession(BaseModel):
    """登录会话（start 到 confirm 之间的临时状态）"""

    uuid_cookie: str
    created_at: str  # ISO 8601
    qrcode_path: str


class SavedAccount(BaseModel):
    """收藏的公众号"""

    fakeid: str
    name: str
    avatar: Optional[str] = None
    signature: Optional[str] = None
    added_at: str  # ISO 8601


class SavedAccounts(BaseModel):
    """收藏列表"""

    accounts: list[SavedAccount] = []


class AccountGroup(BaseModel):
    """公众号分组"""

    name: str
    accounts: list[str] = []  # 存公众号名称


class Groups(BaseModel):
    """分组列表"""

    groups: list[AccountGroup] = []


def _wechat_dir() -> Path:
    return get_data_dir("wechat_article")


# --- 凭证 ---


def save_credentials(credentials: Credentials) -> Path:
    path = _wechat_dir() / "credentials.json"
    path.write_text(
        json.dumps(credentials.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def load_credentials() -> Optional[Credentials]:
    path = _wechat_dir() / "credentials.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Credentials(**data)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("凭证文件损坏或格式不兼容：path={} error={}", path, e)
        return None


def is_credentials_valid(credentials: Credentials) -> bool:
    expires_at = datetime.fromisoformat(credentials.expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < expires_at


# --- 登录会话 ---


def save_login_session(session: LoginSession) -> Path:
    path = _wechat_dir() / "login_session.json"
    path.write_text(
        json.dumps(session.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def load_login_session() -> Optional[LoginSession]:
    path = _wechat_dir() / "login_session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LoginSession(**data)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("登录会话文件损坏：path={} error={}", path, e)
        return None


def clear_login_session() -> None:
    path = _wechat_dir() / "login_session.json"
    if path.exists():
        path.unlink()


def get_qrcode_path() -> Path:
    return _wechat_dir() / "login_qrcode.png"


# --- 收藏公众号 ---


def load_saved_accounts() -> SavedAccounts:
    path = _wechat_dir() / "saved_accounts.json"
    if not path.exists():
        return SavedAccounts()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SavedAccounts(**data)
    except (json.JSONDecodeError, ValueError, KeyError):
        return SavedAccounts()


def save_saved_accounts(accounts: SavedAccounts) -> None:
    path = _wechat_dir() / "saved_accounts.json"
    path.write_text(
        json.dumps(accounts.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_account_by_name(name: str) -> Optional[SavedAccount]:
    """按名称查找已保存的公众号"""
    saved = load_saved_accounts()
    for acc in saved.accounts:
        if acc.name == name:
            return acc
    return None


def find_account_by_fakeid(fakeid: str) -> Optional[SavedAccount]:
    """按 fakeid 查找已保存的公众号"""
    saved = load_saved_accounts()
    for acc in saved.accounts:
        if acc.fakeid == fakeid:
            return acc
    return None


# --- 分组 ---


def _groups_path() -> Path:
    return _wechat_dir() / "groups.json"


def load_groups() -> Groups:
    path = _groups_path()
    if not path.exists():
        return Groups()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Groups(**data)
    except (json.JSONDecodeError, ValueError, KeyError):
        return Groups()


def save_groups(groups: Groups) -> None:
    path = _groups_path()
    path.write_text(
        json.dumps(groups.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --- 搜索缓存 ---


def save_search_cache(results: list[dict]) -> None:
    """缓存最近一次搜索结果，供 account add 使用"""
    path = _wechat_dir() / "cached_accounts.json"
    path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_search_cache() -> list[dict]:
    path = _wechat_dir() / "cached_accounts.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


# --- 任务定义 + 执行记录 ---


class TaskConfig(BaseModel):
    """任务配置"""

    accounts: list[str] = Field(default_factory=list)
    group: Optional[str] = None
    article_count: int = Field(default=5, ge=1, le=100)
    account_interval: float = Field(default=10.0, ge=0)
    after_date: Optional[str] = None
    fetch_content: bool = True
    content_concurrency: int = Field(default=3, ge=1, le=20)


class TaskDefinition(BaseModel):
    """任务定义（可复用模板）"""

    task_id: str
    name: str = ""
    created_at: str
    config: TaskConfig


class AccountProgress(BaseModel):
    """单个公众号的爬取进度"""

    name: str
    fakeid: str
    status: str = "pending"  # pending / running / completed / failed
    articles_found: int = 0
    articles_new: int = 0
    articles_cached: int = 0
    content_failed: int = 0
    error: Optional[str] = None


class RunStatistics(BaseModel):
    """执行统计"""

    total_accounts: int = 0
    completed_accounts: int = 0
    failed_accounts: int = 0
    total_articles: int = 0
    new_articles: int = 0
    cached_articles: int = 0
    content_failed: int = 0


class Run(BaseModel):
    """一次任务执行"""

    run_id: str
    task_id: str
    status: str = "pending"  # pending / running / completed / failed
    created_at: str
    updated_at: str
    config: TaskConfig  # 快照，执行时从 task 复制
    progress: list[AccountProgress] = []
    statistics: RunStatistics = RunStatistics()
    articles: list[dict] = []


# --- Task IO（单文件 tasks.json）---


def _tasks_path() -> Path:
    return _wechat_dir() / "tasks.json"


def load_all_tasks() -> list[TaskDefinition]:
    path = _tasks_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [TaskDefinition(**t) for t in data]
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("任务列表文件损坏：path={} error={}", path, e)
        return []


def save_all_tasks(tasks: list[TaskDefinition]) -> None:
    path = _tasks_path()
    path.write_text(
        json.dumps([t.model_dump() for t in tasks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_task(task_id: str) -> Optional[TaskDefinition]:
    return next((t for t in load_all_tasks() if t.task_id == task_id), None)


# --- Run IO（每次执行一个文件）---


def _runs_dir() -> Path:
    d = _wechat_dir() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_run(run: Run) -> None:
    path = _runs_dir() / f"{run.run_id}.json"
    path.write_text(
        json.dumps(run.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_run(run_id: str) -> Optional[Run]:
    path = _runs_dir() / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Run(**data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("执行记录文件损坏：path={} error={}", path, e)
        return None


def list_run_ids() -> list[str]:
    """列出所有 run ID（按时间倒序）"""
    d = _runs_dir()
    files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [f.stem for f in files]
