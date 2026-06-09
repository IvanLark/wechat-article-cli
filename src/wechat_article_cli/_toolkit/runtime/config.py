"""配置加载与优先级合并。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from wechat_article_cli._toolkit.runtime.home import get_config_path
from wechat_article_cli._toolkit.runtime.state import read_yaml, write_yaml


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def merge_config(
    cli_values: Mapping[str, Any] | None = None,
    env_values: Mapping[str, Any] | None = None,
    file_values: Mapping[str, Any] | None = None,
    defaults: Mapping[str, Any] | None = None,
    *,
    env_as_fallback: bool = False,
) -> dict[str, Any]:
    """合并配置层。

    默认顺序：参数 > env > 文件 > 默认值
    当 `env_as_fallback=True` 时：参数 > 文件 > env > 默认值
    """
    merged: dict[str, Any] = deepcopy(dict(defaults or {}))
    ordered_layers = (
        [env_values or {}, file_values or {}, cli_values or {}]
        if env_as_fallback
        else [file_values or {}, env_values or {}, cli_values or {}]
    )
    for layer in ordered_layers:
        merged = _deep_merge(merged, layer)
    return merged


def load_config_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = read_yaml(path, default={})
    return data if isinstance(data, dict) else {}


def load_capability_config(
    capability_name: str,
    model: type[BaseModel],
    *,
    cli_values: Mapping[str, Any] | None = None,
    env_values: Mapping[str, Any] | None = None,
    file_path: Path | None = None,
    env_as_fallback: bool = False,
) -> BaseModel:
    path = file_path or get_config_path(capability_name)
    file_values = load_config_file(path if path.exists() else None)
    defaults = model.model_construct().model_dump(exclude_none=False)
    merged = merge_config(
        cli_values=cli_values,
        env_values=env_values,
        file_values=file_values,
        defaults=defaults,
        env_as_fallback=env_as_fallback,
    )
    return model.model_validate(merged)


def load_capability_config_data(capability_name: str, *, file_path: Path | None = None) -> dict[str, Any]:
    path = file_path or get_config_path(capability_name)
    return load_config_file(path if path.exists() else None)


def write_capability_config_data(
    capability_name: str,
    data: Mapping[str, Any],
    *,
    file_path: Path | None = None,
) -> Path:
    path = file_path or get_config_path(capability_name)
    write_yaml(path, dict(data))
    return path


def set_dotted_value(target: dict[str, Any], dotted_key: str, value: Any) -> dict[str, Any]:
    parts = [part.strip() for part in dotted_key.split(".") if part.strip()]
    if not parts:
        raise ValueError("配置 key 不能为空")

    cursor = target
    for part in parts[:-1]:
        existing = cursor.get(part)
        if existing is None:
            cursor[part] = {}
        elif not isinstance(existing, dict):
            raise ValueError(f"配置 key 冲突：{part} 不是对象")
        cursor = cursor[part]
    cursor[parts[-1]] = value
    return target


def unset_dotted_value(target: dict[str, Any], dotted_key: str) -> dict[str, Any]:
    parts = [part.strip() for part in dotted_key.split(".") if part.strip()]
    if not parts:
        raise ValueError("配置 key 不能为空")

    stack: list[tuple[dict[str, Any], str]] = []
    cursor = target
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            return target
        stack.append((cursor, part))
        cursor = next_value

    cursor.pop(parts[-1], None)

    while stack:
        parent, part = stack.pop()
        child = parent.get(part)
        if isinstance(child, dict) and not child:
            parent.pop(part, None)
        else:
            break
    return target


def dump_default_config(model: type[BaseModel]) -> str:
    import tempfile

    from wechat_article_cli._toolkit.runtime.state import write_yaml  # 避免顶层循环引用

    instance = model.model_construct()
    data = instance.model_dump(exclude_none=False)
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "config.yml"
        write_yaml(path, data)
        return path.read_text(encoding="utf-8")
