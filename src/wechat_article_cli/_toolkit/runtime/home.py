"""Capability home 与运行时路径约定。"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _expand_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _normalize_name(name: str) -> str:
    return name.strip().replace("_", "-")


def _capability_env_name(name: str) -> str:
    normalized = _normalize_name(name).replace("-", "_").upper()
    return f"{normalized}_HOME"


def _ensure_secure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def get_capability_home(name: str, *, default_dirname: str | None = None) -> Path:
    """返回 capability home 目录。

    优先级：
    1. <CAPABILITY>_HOME
    2. WECHAT_ARTICLE_CLI_HOME/<capability>
    3. ~/.<tool-name>
    """
    normalized = _normalize_name(name)
    env_name = _capability_env_name(normalized)

    if raw := os.environ.get(env_name):
        home = _expand_path(raw)
    elif raw := os.environ.get("WECHAT_ARTICLE_CLI_HOME"):
        home = _expand_path(raw) / normalized
    else:
        dirname = default_dirname or normalized
        home = Path.home() / f".{dirname}"

    return _ensure_secure_dir(home)


def ensure_subdir(name: str, *parts: str, default_dirname: str | None = None) -> Path:
    """返回 capability home 下的子目录，并确保存在。"""
    return _ensure_secure_dir(
        get_capability_home(name, default_dirname=default_dirname).joinpath(*parts)
    )


def get_credentials_path(name: str, *, default_dirname: str | None = None) -> Path:
    return get_capability_home(name, default_dirname=default_dirname) / "credentials.json"


def get_config_path(name: str, *, default_dirname: str | None = None) -> Path:
    return get_capability_home(name, default_dirname=default_dirname) / "config.yml"


def get_cache_dir(name: str, *, default_dirname: str | None = None) -> Path:
    return ensure_subdir(name, "cache", default_dirname=default_dirname)


def get_state_dir(name: str, *, default_dirname: str | None = None) -> Path:
    return ensure_subdir(name, "state", default_dirname=default_dirname)


def get_logs_dir(name: str, *, default_dirname: str | None = None) -> Path:
    return ensure_subdir(name, "logs", default_dirname=default_dirname)


def get_tmp_dir(name: str, *, default_dirname: str | None = None) -> Path:
    return ensure_subdir(name, "tmp", default_dirname=default_dirname)


def get_data_dir(name: str, *, default_dirname: str | None = None) -> Path:
    """兼容旧调用方的别名，语义等同于 capability home。"""
    return get_capability_home(name, default_dirname=default_dirname)
