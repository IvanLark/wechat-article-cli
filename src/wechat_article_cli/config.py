"""wechat-article 本地配置。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from wechat_article_cli._toolkit.runtime.config import set_dotted_value, unset_dotted_value
from wechat_article_cli._toolkit.runtime.home import get_config_path
from wechat_article_cli._toolkit.runtime.state import read_yaml, write_yaml

CAPABILITY_NAME = "wechat_article"
CONFIG_KEYS = {"proxy.url", "proxy.token"}


class ProxyConfig(BaseModel):
    url: list[str] = Field(default_factory=list)
    token: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "url" not in value and "urls" in value:
            value = {**value, "url": value["urls"]}
        return value

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: Any) -> list[str]:
        return normalize_proxy_urls(value)

    @field_validator("token", mode="before")
    @classmethod
    def normalize_token(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


class AppConfig(BaseModel):
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)


def normalize_proxy_urls(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        raise ValueError("proxy.url 必须是字符串或字符串数组")

    urls: list[str] = []
    seen: set[str] = set()
    for item in parts:
        if not isinstance(item, str):
            raise ValueError("proxy.url 数组里只能包含字符串")
        url = item.strip().rstrip("/")
        if not url:
            continue
        if url in seen:
            continue
        urls.append(url)
        seen.add(url)
    return urls


def get_app_config_path() -> Path:
    return get_config_path(CAPABILITY_NAME)


def load_config_data() -> dict[str, Any]:
    path = get_app_config_path()
    data = read_yaml(path, default={})
    return data if isinstance(data, dict) else {}


def write_config_data(data: dict[str, Any]) -> Path:
    return write_yaml(get_app_config_path(), _prune_empty(data), secure=True)


def load_file_config() -> AppConfig:
    return AppConfig.model_validate(load_config_data())


def load_effective_config() -> AppConfig:
    data = load_config_data()
    proxy_data = data.setdefault("proxy", {})
    if not isinstance(proxy_data, dict):
        proxy_data = {}
        data["proxy"] = proxy_data

    raw_proxy_url = os.environ.get("WECHAT_PROXY_URL", "")
    raw_proxy_token = os.environ.get("WECHAT_PROXY_TOKEN", "")
    if raw_proxy_url.strip():
        proxy_data["url"] = raw_proxy_url
    if raw_proxy_token.strip():
        proxy_data["token"] = raw_proxy_token
    return AppConfig.model_validate(data)


def get_proxy_urls() -> list[str]:
    return load_effective_config().proxy.url


def get_proxy_token() -> str:
    return load_effective_config().proxy.token


def set_config_value(key: str, raw_value: str) -> dict[str, Any]:
    normalized_key = normalize_config_key(key)
    value = normalize_config_value(normalized_key, raw_value)
    data = load_config_data()
    set_dotted_value(data, normalized_key, value)
    path = write_config_data(data)
    return {
        "path": str(path),
        "key": normalized_key,
        "action": "set",
        "value": _sanitize_value(normalized_key, value),
    }


def unset_config_value(key: str) -> dict[str, Any]:
    normalized_key = normalize_config_key(key)
    data = load_config_data()
    unset_dotted_value(data, normalized_key)
    path = write_config_data(data)
    return {
        "path": str(path),
        "key": normalized_key,
        "action": "unset",
        "value": None,
    }


def build_config_show_payload() -> dict[str, Any]:
    path = get_app_config_path()
    file_config = load_file_config()
    effective_config = load_effective_config()
    return {
        "path": str(path),
        "exists": path.exists(),
        "values": sanitize_config(file_config),
        "effective": sanitize_config(effective_config),
        "sources": {
            "proxy.url": _source_for_proxy_url(file_config),
            "proxy.token": _source_for_proxy_token(file_config),
        },
    }


def build_config_path_payload() -> dict[str, Any]:
    path = get_app_config_path()
    return {
        "path": str(path),
        "exists": path.exists(),
    }


def normalize_config_key(key: str) -> str:
    normalized = key.strip()
    if normalized == "proxy.urls":
        normalized = "proxy.url"
    if normalized not in CONFIG_KEYS:
        allowed = "、".join(sorted(CONFIG_KEYS))
        raise ValueError(f"未知配置 key：{key}，可选：{allowed}")
    return normalized


def normalize_config_value(key: str, raw_value: str) -> Any:
    if key == "proxy.url":
        urls = normalize_proxy_urls(raw_value)
        if not urls:
            raise ValueError("proxy.url 不能为空")
        return urls
    if key == "proxy.token":
        token = raw_value.strip()
        if not token:
            raise ValueError("proxy.token 不能为空")
        return token
    raise ValueError(f"未知配置 key：{key}")


def sanitize_config(config: AppConfig) -> dict[str, Any]:
    data = config.model_dump(mode="json")
    token = data.get("proxy", {}).get("token", "")
    if token:
        data["proxy"]["token"] = mask_secret(token)
    return data


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}...{value[-3:]}"


def _sanitize_value(key: str, value: Any) -> Any:
    if key == "proxy.token":
        return mask_secret(str(value))
    return value


def _source_for_proxy_url(file_config: AppConfig) -> Literal["env", "config", "missing"]:
    if "WECHAT_PROXY_URL" in os.environ and os.environ.get("WECHAT_PROXY_URL", "").strip():
        return "env"
    if file_config.proxy.url:
        return "config"
    return "missing"


def _source_for_proxy_token(file_config: AppConfig) -> Literal["env", "config", "missing"]:
    if "WECHAT_PROXY_TOKEN" in os.environ and os.environ.get("WECHAT_PROXY_TOKEN", "").strip():
        return "env"
    if file_config.proxy.token:
        return "config"
    return "missing"


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned = {
            key: _prune_empty(item)
            for key, item in value.items()
            if item not in (None, "", [], {})
        }
        return {
            key: item
            for key, item in cleaned.items()
            if item not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [_prune_empty(item) for item in value if item not in (None, "", [], {})]
    return value
