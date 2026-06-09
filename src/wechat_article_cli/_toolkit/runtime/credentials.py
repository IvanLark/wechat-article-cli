"""凭证文件读写与 fallback 约定。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wechat_article_cli._toolkit.runtime.config import (
    merge_config,
    set_dotted_value,
    unset_dotted_value,
)
from wechat_article_cli._toolkit.runtime.home import get_credentials_path
from wechat_article_cli._toolkit.runtime.state import read_json, write_json


def load_credentials_file(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = read_json(path, default={})
    return data if isinstance(data, dict) else {}


def load_capability_credentials(
    capability_name: str,
    model: type[BaseModel],
    *,
    env_values: Mapping[str, Any] | None = None,
    file_path: Path | None = None,
) -> BaseModel:
    path = file_path or get_credentials_path(capability_name)
    file_values = load_credentials_file(path if path.exists() else None)
    defaults = model.model_construct().model_dump(exclude_none=False)
    merged = merge_config(
        env_values=env_values,
        file_values=file_values,
        defaults=defaults,
        env_as_fallback=True,
    )
    return model.model_validate(merged)


def load_capability_credentials_data(
    capability_name: str,
    *,
    file_path: Path | None = None,
) -> dict[str, Any]:
    path = file_path or get_credentials_path(capability_name)
    return load_credentials_file(path if path.exists() else None)


def write_capability_credentials_data(
    capability_name: str,
    data: Mapping[str, Any],
    *,
    file_path: Path | None = None,
) -> Path:
    path = file_path or get_credentials_path(capability_name)
    write_json(path, dict(data), secure=True)
    return path


def set_capability_secret(
    capability_name: str,
    dotted_key: str,
    value: str,
    *,
    model: type[BaseModel],
    file_path: Path | None = None,
) -> tuple[BaseModel, Path]:
    path = file_path or get_credentials_path(capability_name)
    raw = load_capability_credentials_data(capability_name, file_path=path)
    set_dotted_value(raw, dotted_key, value)
    validated = model.model_validate(raw)
    write_capability_credentials_data(
        capability_name,
        validated.model_dump(exclude_none=False),
        file_path=path,
    )
    return validated, path


def unset_capability_secret(
    capability_name: str,
    dotted_key: str,
    *,
    model: type[BaseModel],
    file_path: Path | None = None,
) -> tuple[BaseModel, Path]:
    path = file_path or get_credentials_path(capability_name)
    raw = load_capability_credentials_data(capability_name, file_path=path)
    unset_dotted_value(raw, dotted_key)
    validated = model.model_validate(raw)
    write_capability_credentials_data(
        capability_name,
        validated.model_dump(exclude_none=False),
        file_path=path,
    )
    return validated, path
