"""状态文件与安全写入辅助。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from pydantic import BaseModel


def _normalize_data(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json", exclude_none=False)
    if is_dataclass(data):
        return asdict(data)
    return data


def _chmod_best_effort(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def atomic_write_text(path: Path, text: str, *, secure: bool = False) -> Path:
    """原子写入文本文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    if secure:
        _chmod_best_effort(tmp_path, 0o600)
    tmp_path.replace(path)
    if secure:
        _chmod_best_effort(path, 0o600)
    return path


def read_json(path: Path, model: type[BaseModel] | None = None, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    data = json.loads(path.read_text(encoding="utf-8"))
    if model is None:
        return data
    return model.model_validate(data)


def write_json(path: Path, data: Any, *, secure: bool = False, compact: bool = False) -> Path:
    payload = _normalize_data(data)
    kwargs: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    return atomic_write_text(path, json.dumps(payload, **kwargs), secure=secure)


def read_yaml(path: Path, model: type[BaseModel] | None = None, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return default
    if model is None:
        return data
    return model.model_validate(data)


def write_yaml(path: Path, data: Any, *, secure: bool = False) -> Path:
    payload = _normalize_data(data)
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    return atomic_write_text(path, text, secure=secure)

