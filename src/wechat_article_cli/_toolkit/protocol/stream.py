"""NDJSON 事件流协议。"""

from __future__ import annotations

from typing import Any


def stream_item(data: Any) -> dict[str, Any]:
    return {"type": "item", "data": data}


def stream_page(page: int, data: Any) -> dict[str, Any]:
    return {"type": "page", "page": page, "data": data}


def stream_done(meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "done", "meta": meta or {}}


def stream_error(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"code": code, "message": message}}

