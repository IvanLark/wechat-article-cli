"""输出渲染层。"""

from __future__ import annotations

from typing import Any

from wechat_article_cli._toolkit.protocol.output import print_json, print_yaml


def render_json(payload: Any, *, compact: bool = False) -> None:
    print_json(payload, compact=compact)


def render_yaml(payload: Any) -> None:
    print_yaml(payload)


def render_human(text: str) -> None:
    print(text)

