"""结构化输出与流式输出辅助。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Iterable

import yaml
from pydantic import BaseModel

from wechat_article_cli._toolkit.protocol.models import ErrorEnvelope, ErrorInfo, SuccessEnvelope


def _normalize_data(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json", exclude_none=False)
    if is_dataclass(data):
        return asdict(data)
    return data


def success(data: Any, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return SuccessEnvelope(data=_normalize_data(data), meta=meta).model_dump(mode="json", exclude_none=True)


def failure(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ErrorEnvelope(error=ErrorInfo(code=code, message=message, details=details)).model_dump(
        mode="json",
        exclude_none=True,
    )


def print_json(payload: Any, *, compact: bool = False) -> None:
    data = _normalize_data(payload)
    kwargs = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    print(json.dumps(data, **kwargs))


def print_yaml(payload: Any) -> None:
    data = _normalize_data(payload)
    print(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def emit_ndjson(events: Iterable[Any]) -> None:
    for event in events:
        print(json.dumps(_normalize_data(event), ensure_ascii=False, separators=(",", ":")))


def print_error_json_and_exit(
    code: str,
    message: str,
    *,
    exit_code: int = 1,
    details: dict[str, Any] | None = None,
) -> None:
    print_json(failure(code, message, details=details))
    raise SystemExit(exit_code)
